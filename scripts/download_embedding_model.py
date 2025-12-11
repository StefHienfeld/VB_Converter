#!/usr/bin/env python3
"""
Script to pre-download the embedding model for semantic analysis.

This downloads ~470MB model which is used for semantic similarity matching.
Run this script once before enabling embeddings to avoid timeout issues.

Usage:
    python scripts/download_embedding_model.py

After successful download, you can enable embeddings in hienfeld/config.py:
    enable_embeddings: bool = True
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hienfeld.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("download_model")


def download_embedding_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
    """
    Download the sentence-transformers model.
    
    Args:
        model_name: HuggingFace model name to download
    """
    try:
        from sentence_transformers import SentenceTransformer
        
        logger.info(f"Downloading embedding model: {model_name}")
        logger.info("This will download ~470MB and may take 5-10 minutes depending on your connection...")
        
        # This will download the model if not already cached
        model = SentenceTransformer(model_name)
        
        # Test the model
        test_embedding = model.encode(["Dit is een test"], convert_to_numpy=True)
        
        logger.info(f"✅ Model downloaded successfully!")
        logger.info(f"   Embedding dimension: {model.get_sentence_embedding_dimension()}")
        logger.info(f"   Cache location: {model._model_card_vars.get('model_name', 'default cache')}")
        logger.info("")
        logger.info("You can now enable embeddings in hienfeld/config.py:")
        logger.info("   enable_embeddings: bool = True")
        
        return True
        
    except ImportError:
        logger.error("❌ sentence-transformers not installed!")
        logger.error("   Install with: pip install sentence-transformers")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to download model: {e}")
        return False


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("Embedding Model Downloader")
    print("="*70 + "\n")
    
    success = download_embedding_model()
    
    if success:
        print("\n✅ Setup complete! Embeddings are ready to use.\n")
        sys.exit(0)
    else:
        print("\n❌ Setup failed. Please check the errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

