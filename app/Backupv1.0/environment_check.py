import os
import torch

print(f"Environment Variables: {os.environ}")
print(f"Torch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")