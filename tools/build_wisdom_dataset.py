import json
import os
import glob

def build_dataset(input_dir, output_file):
    # Find all synthesis json files
    synthesis_files = glob.glob(os.path.join(input_dir, "*teaching_synthesis*.json"))
    insight_files = glob.glob(os.path.join(input_dir, "*insights*.json"))
    
    dataset = []
    
    system_prompt = (
        "You are the Buddhi (discriminating intelligence) of the Vedic memory architecture. "
        "Your role is not to recall raw facts, but to synthesize deep wisdom, interpreting "
        "scriptural episodes through the esoteric lens of Kriya Yoga and the unmanifest Time. "
        "When presented with a core truth and citations, provide the deep structural and spiritual synthesis."
    )
    
    # Process Synthesis Files
    for file_path in synthesis_files:
        print(f"Processing synthesis file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
            
        clusters = []
        if isinstance(content, dict) and "data" in content and "clusters" in content["data"]:
            clusters = content["data"]["clusters"]
        elif isinstance(content, dict) and "clusters" in content:
            clusters = content["clusters"]
        elif isinstance(content, list):
            clusters = content
            
        for cluster in clusters:
            core_truth = cluster.get("core_truth")
            lens_synthesis = cluster.get("lens_synthesis")
            verse_citations = cluster.get("verse_citations", [])
            
            if not core_truth or not lens_synthesis:
                continue
                
            user_message = f"Synthesize the inner meaning of this core truth:\n\n{core_truth}\n\nRelated Verses: {', '.join(verse_citations)}"
            
            example = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": lens_synthesis}
                ]
            }
            dataset.append(example)

    # Process Insight Files
    for file_path in insight_files:
        print(f"Processing insight file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
            
        insights = []
        if isinstance(content, dict) and "data" in content and "insights" in content["data"]:
            insights = content["data"]["insights"]
        elif isinstance(content, dict) and "insights" in content:
            insights = content["insights"]
        elif isinstance(content, list):
            insights = content
            
        for ins in insights:
            title = ins.get("title")
            insight_text = ins.get("insight")
            evidence = ins.get("evidence", [])
            cross_refs = ins.get("cross_references", [])
            
            if not title or not insight_text:
                continue
                
            user_message = f"Provide a deep structural or theological insight regarding this pattern:\n\n{title}\n\nEvidence: {'; '.join(evidence)}"
            
            assistant_response = insight_text
            if cross_refs:
                assistant_response += f"\n\nCross References: {'; '.join(cross_refs)}"
                
            example = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response}
                ]
            }
            dataset.append(example)
            
    # Write output
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for ex in dataset:
            out_f.write(json.dumps(ex) + "\n")
            
    print(f"Dataset generated with {len(dataset)} examples at {output_file}")

if __name__ == "__main__":
    input_directory = "/Users/badenath/projects/vedic puran/purangpt/tools/read_pass/out"
    output_filename = "/Users/badenath/projects/vedic puran/purangpt/tools/read_pass/out/wisdom_buddhi_dataset.jsonl"
    build_dataset(input_directory, output_filename)
