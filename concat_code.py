import os

def main():
    root_dir = "."
    templates_dir = "./templates"
    output_file = "./instance/combined_codebase.txt"

    # The file(s) you want to exclude from the root directory.
    excluded_root_files = ["concat_code.py"]  # Change or add more filenames here

    # 1. Gather all .py files in the root folder, excluding the ones listed
    py_files = [
        f for f in os.listdir(root_dir) 
        if f.endswith(".py") and f not in excluded_root_files
    ]

    # 2. Gather all .html files in the templates folder
    html_files = [
        f for f in os.listdir(templates_dir) 
        if f.endswith(".html")
    ]

    # 3. Write everything into one file
    with open(output_file, "w", encoding="utf-8") as outfile:
        # Write .py files first
        for f in py_files:
            file_path = os.path.join(root_dir, f)
            outfile.write(f"--- Start of {f} ---\n")
            with open(file_path, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
            outfile.write(f"\n--- End of {f} ---\n\n")

        # Then write .html files
        for f in html_files:
            file_path = os.path.join(templates_dir, f)
            outfile.write(f"--- Start of {f} ---\n")
            with open(file_path, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
            outfile.write(f"\n--- End of {f} ---\n\n")

if __name__ == "__main__":
    main()
