import ollama
import subprocess
import os
import re

class LLMCompiler:
    def __init__(self, log_callback, model_name="llama3.2"):
        self.model_name = model_name
        self.tectonic_path = os.path.join("engines", "tectonic.exe")
        self.log = log_callback

    def generate_summary(self, transcript, context):
        """Sends data to Ollama and returns professional LaTeX code."""
        system_prompt = (
            "You are a professional meeting assistant. Use the provided transcript "
            "and supporting materials to create a highly structured summary. "
            "Output the ENTIRE response as a valid, compilable LaTeX document using the 'article' class. "
            "CRITICAL RULES FOR LATEX: "
            "1. You MUST include \\usepackage{fontspec} in your preamble to support unicode characters like dashes and quotes. "
            "2. You MUST escape all special LaTeX characters in the text body (e.g., use \\$ for currency, \\% for percentages, \\& for and). "
            "Include sections for 'Executive Summary', 'Key Discussion Points', and 'Action Items' (use a table). "
            "Return ONLY the raw LaTeX code. Do not wrap it in markdown backticks."
        )
        
        user_prompt = f"Supporting Materials:\n{context}\n\nMeeting Transcript:\n{transcript}"
        
        self.log(f"[*] Querying {self.model_name} (10m Keep-Alive)...")
        
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                options={
                    "num_ctx": 8192,  
                    "temperature": 0.2 
                },
                keep_alive="10m" 
            )
            
            # Clean up the output just in case the LLM still wraps it in markdown
            latex_code = response['message']['content']
            if latex_code.startswith("```latex"):
                latex_code = latex_code.split("```latex")[1]
            if latex_code.endswith("```"):
                latex_code = latex_code.rsplit("```", 1)[0]
                
            return latex_code.strip()
            
        except Exception as e:
            self.log(f"[-] Ollama Error: {e}")
            raise e

    def compile_to_pdf(self, latex_content, output_name="Meeting_Summary"):
        """Compiles LaTeX string into a PDF using Tectonic with sanitized paths."""
        
        # 1. Sanitize the filename! Replace spaces and weird characters with underscores
        safe_name = re.sub(r'[^A-Za-z0-9_\-]', '_', output_name)
        
        # 2. Get absolute paths to avoid folder confusion
        base_dir = os.path.abspath(os.getcwd())
        exports_dir = os.path.join(base_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        
        tex_file = os.path.join(exports_dir, f"{safe_name}.tex")
        tectonic_exe = os.path.join(base_dir, "engines", "tectonic.exe")
        
        # Save LaTeX content to file
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(latex_content)
        
        self.log(f"[*] Compiling PDF via Tectonic ({safe_name}.pdf)...")
        try:
            result = subprocess.run(
                [tectonic_exe, tex_file],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            else:
                self.log(f"[-] LaTeX Error: {result.stderr}")
                return False
        except Exception as e:
            self.log(f"[-] Compilation Engine Error: {e}")
            return False