import ollama

class OllamaEngine:
    def __init__(self, default_model='mistral'):
        self.model = default_model

    def is_running(self):
        """Checks if the local Ollama service is active and responding."""
        try:
            ollama.list()
            return True
        except Exception:
            return False

    def generate_answer(self, context, question):
        """Standard non-streaming generation (used for backward compatibility)."""
        prompt = f"Use the following context to answer the question.\n\nContext:\n{context}\n\nQuestion: {question}"
        
        try:
            response = ollama.generate(
                model=self.model, 
                prompt=prompt,
                options={
                    "num_gpu": 6,    # Only put 6 layers on the GPU to prevent crashing
                    "num_ctx": 2048  # Restrict the AI's memory window to save VRAM
                }
            )
            return response['response']
        except Exception as e:
            return f"Error generating response: {str(e)}"

    def stream_answer(self, context, question):
        """Streams the generation token-by-token in real-time."""
        prompt = f"Use the following context to answer the question.\n\nContext:\n{context}\n\nQuestion: {question}"
        
        try:
            response_stream = ollama.generate(
                model=self.model, 
                prompt=prompt, 
                stream=True,
                options={
                    "num_gpu": 6,    # Only put 6 layers on the GPU to prevent crashing
                    "num_ctx": 2048  # Restrict the AI's memory window to save VRAM
                }
            )
            
            for chunk in response_stream:
                if 'response' in chunk:
                    yield chunk['response']
        except Exception as e:
            yield f"Error generating response: {str(e)}"