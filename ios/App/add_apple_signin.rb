#!/usr/bin/env ruby
# Adds the native Sign in with Apple files to the App target, wires the
# entitlements file, and enables the Sign in with Apple capability so automatic
# signing (-allowProvisioningUpdates) provisions it on the App ID. Idempotent:
# re-running skips files already referenced and just re-asserts the settings.
require 'xcodeproj'

project_path = File.join(__dir__, 'App.xcodeproj')
project = Xcodeproj::Project.open(project_path)

target = project.targets.find { |t| t.name == 'App' }
abort 'App target not found' unless target

# Paths relative to SOURCE_ROOT (the App.xcodeproj dir), matching how the
# existing Native files are referenced (path = App/Native/...).
swift_files = [
  'App/Native/Auth/AppleSignIn.swift',
  'App/Native/Views/SignInView.swift',
]

existing_paths = project.files.map(&:path).compact
main_group = project.main_group

added = []
swift_files.each do |rel|
  next if existing_paths.include?(rel)
  ref = main_group.new_reference(rel)
  ref.name = File.basename(rel)
  ref.source_tree = 'SOURCE_ROOT'
  ref.last_known_file_type = 'sourcecode.swift'
  target.source_build_phase.add_file_reference(ref, true)
  added << rel
end

# Reference the entitlements file (not compiled — just present in the project).
ent_rel = 'App/App.entitlements'
unless existing_paths.include?(ent_rel)
  ent = main_group.new_reference(ent_rel)
  ent.name = 'App.entitlements'
  ent.source_tree = 'SOURCE_ROOT'
  ent.last_known_file_type = 'text.plist.entitlements'
end

# Point every build config at the entitlements file (Debug + Release).
target.build_configurations.each do |cfg|
  cfg.build_settings['CODE_SIGN_ENTITLEMENTS'] = ent_rel
end

# Declare the Sign in with Apple capability so automatic signing registers it
# on the App ID when archiving with -allowProvisioningUpdates.
attrs = (project.root_object.attributes['TargetAttributes'] ||= {})
tattr = (attrs[target.uuid] ||= {})
caps  = (tattr['SystemCapabilities'] ||= {})
caps['com.apple.developer.applesignin'] = { 'enabled' => 1 }

project.save

puts 'ADDED:'
added.each { |f| puts "  + #{f}" }
puts "  (no new swift files)" if added.empty?
puts "CODE_SIGN_ENTITLEMENTS = #{ent_rel} on #{target.build_configurations.size} configs"
puts 'Sign in with Apple capability: enabled'
puts 'DONE'
