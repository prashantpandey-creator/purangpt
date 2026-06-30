import SwiftUI
import MetalKit
import simd
import os

// ============================================================================
//  BinduMetalView — native Metal host for the "Eye of the Void" orb.
//
//  Drop-in for the chat backdrop:
//
//      BinduOrbView(level: viewModel.orbLevel)   // 0..1 energy/activity
//
//  It wraps an MTKView whose internal display link drives the orb at the
//  device's native refresh (60 / 120fps ProMotion). The shader lives in
//  Bindu/Shaders.metal (namespace `bindu`, entries bindu_orb_vertex /
//  bindu_orb_fragment), compiled into the default .metallib.
//
//  Composites over the dark Twilight-Sanctum background: the view is non-opaque
//  with a clear background and premultiplied-alpha blending, so only the orb's
//  light shows.
//
//  Reduce-motion aware: when UIAccessibility.isReduceMotionEnabled is on, the
//  display loop is paused and a single static frame is rendered (mirrors the
//  web's `reduced` guard).
// ============================================================================

/// CPU-side mirror of `bindu::Uniforms` in Shaders.metal.
/// Field order + types MUST match (float, float, float2 → 16-byte aligned).
private struct BinduUniforms {
    var uTime: Float
    var uLevel: Float
    var uRes: SIMD2<Float>
}

// MARK: - Public SwiftUI view

/// The orb, ready to drop behind chat content. `level` eases toward the eye's
/// energy each frame (0 = calm idle eye, 1 = the eye flaring at full activity).
public struct BinduOrbView: View {
    private let level: Double

    /// False while the orb is offscreen (parent disappeared) — drives the
    /// MTKView's `isPaused` so the heavy fragment shader stops running when the
    /// view is not on screen.
    ///
    /// NOTE: we DELIBERATELY do NOT gate on `@Environment(\.scenePhase)` here.
    /// This SwiftUI tree is hosted inside a bare `UIHostingController` from a
    /// UIKit `AppDelegate` (see NativeRootHosting.swift) — there is no SwiftUI
    /// `Scene`, so `scenePhase` never advances to `.active` and stays stuck at
    /// its default. Gating on it left `active` permanently false, the MTKView
    /// permanently paused, `draw(in:)` never called, and the orb rendered as the
    /// MTKView's blank gray default surface (the "flat gray rectangle" bug). The
    /// app-backgrounded pause that `scenePhase` was meant to provide is instead
    /// handled reliably inside the Coordinator via `UIApplication` active/resign
    /// notifications, which DO fire under UIKit hosting.
    @State private var isVisible = false

    public init(level: Double = 0.0) {
        self.level = level
    }

    public var body: some View {
        BinduMetalView(level: level, active: isVisible)
            .ignoresSafeArea()
            .allowsHitTesting(false)   // pure backdrop; never steals touches
            .onAppear { isVisible = true }
            .onDisappear { isVisible = false }
    }
}

// MARK: - UIViewRepresentable host

struct BinduMetalView: UIViewRepresentable {
    var level: Double
    /// When false the render loop is paused (orb offscreen or app not active).
    var active: Bool = true

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> MTKView {
        let view = MTKView()
        context.coordinator.configure(view)
        context.coordinator.targetLevel = Float(level)
        context.coordinator.active = active
        context.coordinator.applyPauseState(to: view)
        return view
    }

    func updateUIView(_ uiView: MTKView, context: Context) {
        // SwiftUI re-invokes this when `level` or `active` changes; the coordinator
        // eases toward the new target each frame and pauses/resumes the loop.
        context.coordinator.targetLevel = Float(level)
        context.coordinator.active = active
        context.coordinator.applyPauseState(to: uiView)
    }

    static func dismantleUIView(_ uiView: MTKView, coordinator: Coordinator) {
        uiView.delegate = nil
        coordinator.teardown()
    }

    // MARK: Coordinator (MTKViewDelegate)

    final class Coordinator: NSObject, MTKViewDelegate {
        private static let log = Logger(subsystem: "com.fcpuru95.purangpt", category: "BinduMetal")

        private var device: MTLDevice?
        private var commandQueue: MTLCommandQueue?
        private var pipelineState: MTLRenderPipelineState?

        private var startTime: CFTimeInterval = 0
        private var hasStart = false

        /// Eased energy/activity level fed to the shader (`u_lv`).
        private var level: Float = 0.0
        /// Target the eased `level` chases (set from SwiftUI `level`).
        var targetLevel: Float = 0.0
        /// False when the orb is offscreen (parent view disappeared) — pauses the
        /// loop so the heavy fragment shader stops running when unseen. Set from
        /// SwiftUI via `isVisible` (onAppear/onDisappear).
        var active: Bool = true
        /// False while the app is backgrounded/inactive. Tracked from
        /// `UIApplication` notifications (NOT SwiftUI `scenePhase`, which is dead
        /// under UIKit `UIHostingController` hosting — see BinduOrbView). The loop
        /// runs only when BOTH `active` (on screen) AND `appActive` (foreground).
        var appActive: Bool = UIApplication.shared.applicationState != .background

        private weak var view: MTKView?
        private var notificationObserver: NSObjectProtocol?
        private var appActiveObserver: NSObjectProtocol?
        private var appResignObserver: NSObjectProtocol?

        func configure(_ view: MTKView) {
            guard let device = MTLCreateSystemDefaultDevice() else {
                // No Metal device (shouldn't happen on real hardware/sim);
                // leave the view blank so chat still renders.
                return
            }
            self.device = device
            self.view = view
            view.device = device
            view.delegate = self

            // Dark-sanctum backstop. The orb's premultiplied output blends over
            // this clear colour, so an OPAQUE TRUE-BLACK (#000000 — the SHIPPED
            // web `globals.css :root --bg-deep`, matching `Color.tsBlack`) gives
            // the orb a dark stage AND — critically — degrades gracefully: if the
            // pipeline ever fails to build, the backdrop falls back to the void
            // instead of flashing the light page background (the old "blank
            // light-gray rectangle" failure mode). True-black (not the stale
            // #0A0810) is what makes the FRAMED hero orb seamless: its square
            // bounds clear to the exact same #000000 as the page base, so no
            // visible box-edge seam shows against the void. Opaque is cheaper.
            view.isOpaque = true
            view.layer.isOpaque = true
            view.backgroundColor = .black
            view.clearColor = MTLClearColor(red: 0, green: 0, blue: 0, alpha: 1.0)
            view.framebufferOnly = true

            // The orb is a slow, breathing backdrop — it does not need ProMotion.
            // Cap at 30fps (was 120): imperceptible for this content and a 4x cut
            // in how often the heavy raymarch fragment shader runs.
            view.preferredFramesPerSecond = 30
            view.enableSetNeedsDisplay = false

            // Render at 1x internal resolution (was the implicit @2x/@3x drawable).
            // The orb is soft/glowing so the downscale is invisible, but it cuts
            // the pixel count — and thus the per-frame raymarch cost — 4–9x. The
            // fragment shader reads drawableSize per-frame for aspect, so nothing
            // else needs to change.
            view.contentScaleFactor = 1.0

            commandQueue = device.makeCommandQueue()
            buildPipeline(for: view)
            applyPauseState(to: view)

            // Re-evaluate the pause/static-frame state if accessibility changes.
            notificationObserver = NotificationCenter.default.addObserver(
                forName: UIAccessibility.reduceMotionStatusDidChangeNotification,
                object: nil, queue: .main
            ) { [weak self, weak view] _ in
                guard let self, let view else { return }
                self.applyPauseState(to: view)
            }

            // Pause the heavy raymarch when the app is backgrounded and resume on
            // foreground. This replaces the dead SwiftUI `scenePhase` gate (which
            // never reports `.active` under UIHostingController hosting), giving
            // back the battery-saving behaviour without freezing the orb forever.
            appResignObserver = NotificationCenter.default.addObserver(
                forName: UIApplication.willResignActiveNotification,
                object: nil, queue: .main
            ) { [weak self, weak view] _ in
                guard let self, let view else { return }
                self.appActive = false
                self.applyPauseState(to: view)
            }
            appActiveObserver = NotificationCenter.default.addObserver(
                forName: UIApplication.didBecomeActiveNotification,
                object: nil, queue: .main
            ) { [weak self, weak view] _ in
                guard let self, let view else { return }
                self.appActive = true
                self.applyPauseState(to: view)
            }
        }

        private func buildPipeline(for view: MTKView) {
            guard let device else {
                Self.log.error("Bindu pipeline: no MTLDevice — orb will not draw.")
                return
            }
            // makeDefaultLibrary() loads the bundled default.metallib. A nil here
            // means Shaders.metal isn't in the App target's Compile Sources.
            guard let library = device.makeDefaultLibrary() else {
                Self.log.error("Bindu pipeline: makeDefaultLibrary() returned nil — Shaders.metal missing from the App target's Compile Sources (no default.metallib). Orb will not draw.")
                return
            }
            // The entry points MUST resolve by their plain (un-namespaced) names.
            // If these go nil again it's almost certainly because the vertex/
            // fragment entries got moved back INSIDE `namespace bindu` in
            // Shaders.metal, which mangles them to `bindu::bindu_orb_*`. Keep the
            // entries at global scope. (functionNames is logged to aid triage.)
            guard let vertexFn = library.makeFunction(name: "bindu_orb_vertex"),
                  let fragmentFn = library.makeFunction(name: "bindu_orb_fragment")
            else {
                Self.log.error("Bindu pipeline: entry point lookup FAILED. Expected 'bindu_orb_vertex' & 'bindu_orb_fragment'. Available functionNames=\(library.functionNames, privacy: .public). (If these are namespaced like 'bindu::…', move the vertex/fragment entries OUT of `namespace bindu`.) Orb will not draw.")
                return
            }

            let desc = MTLRenderPipelineDescriptor()
            desc.vertexFunction = vertexFn
            desc.fragmentFunction = fragmentFn

            let color = desc.colorAttachments[0]!
            color.pixelFormat = view.colorPixelFormat
            // Premultiplied-alpha blending — matches the shader's premultiplied
            // output and the web's gl.blendFunc(ONE, ONE_MINUS_SRC_ALPHA).
            color.isBlendingEnabled = true
            color.rgbBlendOperation = .add
            color.alphaBlendOperation = .add
            color.sourceRGBBlendFactor = .one
            color.sourceAlphaBlendFactor = .one
            color.destinationRGBBlendFactor = .oneMinusSourceAlpha
            color.destinationAlphaBlendFactor = .oneMinusSourceAlpha

            // LOUD do/catch: never swallow the pipeline-build error again. A
            // `try?` here is what hid the original "blank orb" regression.
            do {
                pipelineState = try device.makeRenderPipelineState(descriptor: desc)
                Self.log.info("Bindu pipeline: built OK — orb live.")
            } catch {
                pipelineState = nil
                Self.log.error("Bindu pipeline: makeRenderPipelineState FAILED: \(String(describing: error), privacy: .public). Orb will not draw.")
            }
        }

        /// Pause the loop when the orb is unseen (offscreen / app backgrounded) or
        /// reduce-motion is on; otherwise run the live loop. When paused under
        /// reduce-motion we still draw exactly one static frame; when paused
        /// because the orb is offscreen/backgrounded we simply stop. "Visible" =
        /// on screen (`active`) AND app in the foreground (`appActive`).
        func applyPauseState(to view: MTKView) {
            let reduceMotion = UIAccessibility.isReduceMotionEnabled
            let visible = active && appActive
            if reduceMotion || !visible {
                view.isPaused = true
                if reduceMotion && visible {
                    // Visible but motion-reduced: render one static frame.
                    view.enableSetNeedsDisplay = true
                    view.setNeedsDisplay()
                } else {
                    view.enableSetNeedsDisplay = false
                }
            } else {
                view.enableSetNeedsDisplay = false
                view.isPaused = false
            }
        }

        func teardown() {
            for obs in [notificationObserver, appActiveObserver, appResignObserver] {
                if let obs { NotificationCenter.default.removeObserver(obs) }
            }
            notificationObserver = nil
            appActiveObserver = nil
            appResignObserver = nil
        }

        // MARK: MTKViewDelegate

        func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {
            // Aspect handled per-frame from drawableSize; nothing to cache.
        }

        func draw(in view: MTKView) {
            guard let commandQueue,
                  let pipelineState,
                  let drawable = view.currentDrawable,
                  let passDescriptor = view.currentRenderPassDescriptor,
                  let commandBuffer = commandQueue.makeCommandBuffer(),
                  let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: passDescriptor)
            else { return }

            let now = CACurrentMediaTime()
            if !hasStart {
                startTime = now
                hasStart = true
                level = targetLevel   // start at target, don't ease up from 0
            }
            let time = Float(now - startTime)

            // Smooth ease toward the target — morphic, never a jump. k = 0.10 at
            // 30fps reaches ~95% of a full idle→surge step (0.25→1.0) in ~28
            // frames ≈ 0.95s, inside the wanted 0.8–1.2s morph window. Static
            // under reduce-motion.
            if !view.isPaused {
                level += (targetLevel - level) * 0.10
            } else {
                level = targetLevel
            }

            let drawableSize = view.drawableSize
            var uniforms = BinduUniforms(
                uTime: time,
                uLevel: level,
                uRes: SIMD2<Float>(Float(drawableSize.width),
                                   Float(max(drawableSize.height, 1)))
            )

            encoder.setRenderPipelineState(pipelineState)
            // stride (not size) for correct 16-byte alignment of float2.
            encoder.setFragmentBytes(&uniforms,
                                     length: MemoryLayout<BinduUniforms>.stride,
                                     index: 0)
            // Fullscreen triangle — no vertex buffer.
            encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
            encoder.endEncoding()

            commandBuffer.present(drawable)
            commandBuffer.commit()
        }
    }
}
