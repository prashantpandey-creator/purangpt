#!/usr/bin/env ruby
# Adds the Tier-0 theme foundation to the App target.
#   - Theme.swift            -> Sources build phase
#   - Native/Fonts/*.ttf     -> Resources build phase (so they ship in the
#                               bundle and Info.plist UIAppFonts can register them)
# Idempotent: skips any file already referenced. Mirrors add_native_files.rb.
require 'xcodeproj'

project_path = File.join(__dir__, 'App.xcodeproj')
project = Xcodeproj::Project.open(project_path)

target = project.targets.find { |t| t.name == 'App' }
abort "App target not found" unless target

# Paths relative to SOURCE_ROOT (the App.xcodeproj dir), matching the existing
# Native files (path = App/Native/...).
swift_files = [
  'App/Native/Theme.swift',
]
font_files = [
  'App/Native/Fonts/Marcellus-Regular.ttf',
  'App/Native/Fonts/Inter-Regular.ttf',
  'App/Native/Fonts/Inter-Medium.ttf',
  'App/Native/Fonts/Inter-SemiBold.ttf',
]

existing_paths = project.files.map(&:path).compact
main_group = project.main_group

added = []
skipped = []

swift_files.each do |rel|
  if existing_paths.include?(rel)
    skipped << rel
    next
  end
  ref = main_group.new_reference(rel)
  ref.name = File.basename(rel)
  ref.source_tree = 'SOURCE_ROOT'
  ref.last_known_file_type = 'sourcecode.swift'
  target.source_build_phase.add_file_reference(ref, true)
  added << rel
end

font_files.each do |rel|
  if existing_paths.include?(rel)
    skipped << rel
    next
  end
  ref = main_group.new_reference(rel)
  ref.name = File.basename(rel)
  ref.source_tree = 'SOURCE_ROOT'
  ref.last_known_file_type = 'file' # ttf — bundled verbatim as a resource
  target.resources_build_phase.add_file_reference(ref, true)
  added << rel
end

project.save

puts "ADDED:"
added.each { |f| puts "  + #{f}" }
puts "SKIPPED (already present):"
skipped.each { |f| puts "  = #{f}" }
puts "DONE"
