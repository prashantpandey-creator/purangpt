#!/usr/bin/env ruby
# Removes the duplicate Puran* chat-stack files from the App target's build
# phases and from the project's file references. Idempotent: silently skips any
# file already absent. Adding a file to disk alone does not add it to the target;
# likewise removing a file from disk does not remove it from the target — this
# script does the pbxproj side. Disk deletion is handled separately.
require 'xcodeproj'

project_path = File.join(__dir__, 'App.xcodeproj')
project = Xcodeproj::Project.open(project_path)

target = project.targets.find { |t| t.name == 'App' }
abort 'App target not found' unless target

# Paths are relative to SOURCE_ROOT (the App.xcodeproj dir), matching how the
# existing Native files are referenced (path = App/Native/...).
to_remove = [
  'App/Native/Chat/PuranChatModels.swift',
  'App/Native/Chat/ChatStreamClient.swift',
  'App/Native/Chat/ChatScreen.swift',
  'App/Native/Chat/PuranAuthAdapter.swift',
]

removed = []
not_found = []

to_remove.each do |rel|
  ref = project.files.find { |f| f.path == rel }
  if ref.nil?
    not_found << rel
    next
  end

  # Drop it from any build phase that includes it (Sources), then remove the
  # file reference itself from the project.
  target.build_phases.each do |phase|
    next unless phase.respond_to?(:files)
    phase.files.dup.each do |bf|
      phase.remove_build_file(bf) if bf.file_ref == ref
    end
  end
  ref.remove_from_project
  removed << rel
end

project.save

puts 'REMOVED FROM TARGET:'
removed.each { |f| puts "  - #{f}" }
puts 'NOT FOUND (already absent):'
not_found.each { |f| puts "  = #{f}" }
puts 'DONE'
