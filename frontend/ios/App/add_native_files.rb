#!/usr/bin/env ruby
# Adds the divided-port native module files to the App target's build phases.
# Idempotent: skips any file already referenced. Swift -> Sources phase,
# .metal -> the same Sources phase (Xcode routes .metal to Metal compilation).
require 'xcodeproj'

project_path = File.join(__dir__, 'App.xcodeproj')
project = Xcodeproj::Project.open(project_path)

target = project.targets.find { |t| t.name == 'App' }
abort "App target not found" unless target

# Paths are relative to SOURCE_ROOT (the App.xcodeproj dir), matching how the
# existing Native files are referenced (path = App/Native/...).
swift_files = [
  'App/Native/Bindu/BinduMetalView.swift',
  'App/Native/Auth/AuthModels.swift',
  'App/Native/Auth/AuthService.swift',
  'App/Native/Models/LanguageStore.swift',
]
metal_files = [
  'App/Native/Bindu/Shaders.metal',
]

# Collect paths already present in the project to stay idempotent.
existing_paths = project.files.map(&:path).compact

main_group = project.main_group

added = []
skipped = []

(swift_files + metal_files).each do |rel|
  if existing_paths.include?(rel)
    skipped << rel
    next
  end

  ref = main_group.new_reference(rel)
  ref.name = File.basename(rel)
  ref.source_tree = 'SOURCE_ROOT'
  ref.last_known_file_type = rel.end_with?('.metal') ? 'sourcecode.metal' : 'sourcecode.swift'

  target.source_build_phase.add_file_reference(ref, true)
  added << rel
end

project.save

puts "ADDED:"
added.each { |f| puts "  + #{f}" }
puts "SKIPPED (already present):"
skipped.each { |f| puts "  = #{f}" }
puts "DONE"
