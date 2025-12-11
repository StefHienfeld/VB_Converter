#!/usr/bin/env python3
"""
Download script for all ML models used by Hienfeld VB Converter.

This script pre-downloads all models to avoid delays during first analysis.
Run once after installation:

    python scripts/download_models.py --mode balanced

Options:
    --mode fast       Download only models for FAST mode (nl_core_news_sm)
    --mode balanced   Download models for BALANCED mode (default)
    --mode accurate   Download all models including ACCURATE mode
    --mode all        Download everything (same as accurate)
    --verify-only     Only verify existing models, do not download
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("⚠️  Install tqdm for progress bars: pip install tqdm")


class ModelDownloader:
    """Downloads and caches ML models for Hienfeld."""

    MODELS = {
        'fast': [
            ('spacy', 'nl_core_news_sm', '14 MB', 'Dutch language model (small)'),
        ],
        'balanced': [
            ('spacy', 'nl_core_news_sm', '14 MB', 'Dutch language model (small)'),
            ('spacy', 'nl_core_news_md', '43 MB', 'Dutch language model (medium)'),
            ('sentence-transformers', 'all-MiniLM-L6-v2', '90 MB', 'Sentence embeddings (fast, multilingual)'),
        ],
        'accurate': [
            ('spacy', 'nl_core_news_sm', '14 MB', 'Dutch language model (small)'),
            ('spacy', 'nl_core_news_md', '43 MB', 'Dutch language model (medium)'),
            ('sentence-transformers', 'all-MiniLM-L6-v2', '90 MB', 'Sentence embeddings (fast)'),
            ('sentence-transformers', 'paraphrase-multilingual-MiniLM-L12-v2', '470 MB',
             'Sentence embeddings (accurate, Dutch-optimized)'),
        ]
    }

    def __init__(self, mode: str = 'balanced'):
        self.mode = mode
        self.models_to_download = self.MODELS.get(mode, self.MODELS['balanced'])

    def check_spacy_model(self, model_name: str) -> bool:
        """Check if a SpaCy model is installed."""
        try:
            import spacy
            spacy.load(model_name)
            return True
        except (ImportError, OSError):
            return False

    def check_sentence_transformer(self, model_name: str) -> bool:
        """Check if a sentence-transformer model is cached."""
        try:
            from pathlib import Path
            cache_folder = Path.home() / ".cache" / "huggingface" / "hub"
            if not cache_folder.exists():
                return False

            # Check if model files exist
            model_slug = model_name.replace("/", "--")
            for item in cache_folder.glob("*"):
                if model_slug in item.name.lower():
                    return True
            return False
        except Exception:
            return False

    def download_spacy_model(self, model_name: str, size: str, description: str) -> bool:
        """Download a SpaCy model."""
        print(f"\n📦 Downloading SpaCy model: {model_name}")
        print(f"   Size: {size} | {description}")

        if self.check_spacy_model(model_name):
            print(f"   ✅ Already installed")
            return True

        try:
            import subprocess
            print(f"   ⬇️  Downloading...")

            # Run spacy download
            result = subprocess.run(
                [sys.executable, "-m", "spacy", "download", model_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"   ✅ Download complete")
                return True
            else:
                print(f"   ❌ Download failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def download_sentence_transformer(self, model_name: str, size: str, description: str) -> bool:
        """Download a sentence-transformer model."""
        print(f"\n📦 Downloading Sentence-Transformer: {model_name}")
        print(f"   Size: {size} | {description}")

        if self.check_sentence_transformer(model_name):
            print(f"   ✅ Already cached")
            return True

        try:
            print(f"   ⬇️  Downloading (this may take 2-5 minutes)...")

            from sentence_transformers import SentenceTransformer

            # Download (uses tqdm internally if available)
            model = SentenceTransformer(model_name)

            print(f"   ✅ Download complete")
            return True
        except ImportError:
            print(f"   ❌ sentence-transformers not installed")
            print(f"      Install with: pip install sentence-transformers")
            return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def download_all(self) -> Tuple[int, int]:
        """
        Download all models for the selected mode.

        Returns:
            Tuple of (successful_downloads, total_models)
        """
        print("=" * 70)
        print(f"🚀 Hienfeld Model Downloader - Mode: {self.mode.upper()}")
        print("=" * 70)

        total = len(self.models_to_download)
        successful = 0

        for model_type, model_name, size, description in self.models_to_download:
            if model_type == 'spacy':
                if self.download_spacy_model(model_name, size, description):
                    successful += 1
            elif model_type == 'sentence-transformers':
                if self.download_sentence_transformer(model_name, size, description):
                    successful += 1

        print("\n" + "=" * 70)
        print(f"✅ Download complete: {successful}/{total} models ready")
        print("=" * 70)

        if successful < total:
            print(f"\n⚠️  {total - successful} model(s) failed to download")
            print("   You can retry later or use a different mode")

        return successful, total

    def verify_all(self) -> None:
        """Verify all models are available."""
        print("\n🔍 Verifying model availability...")

        all_ok = True
        for model_type, model_name, size, description in self.models_to_download:
            if model_type == 'spacy':
                ok = self.check_spacy_model(model_name)
            else:
                ok = self.check_sentence_transformer(model_name)

            status = "✅" if ok else "❌"
            print(f"   {status} {model_name}")

            if not ok:
                all_ok = False

        if all_ok:
            print("\n✅ All models verified and ready!")
        else:
            print("\n⚠️  Some models are missing - rerun script to download")


def main():
    parser = argparse.ArgumentParser(
        description="Download ML models for Hienfeld VB Converter"
    )
    parser.add_argument(
        '--mode',
        choices=['fast', 'balanced', 'accurate', 'all'],
        default='balanced',
        help='Download mode (default: balanced)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing models, do not download'
    )

    args = parser.parse_args()

    # Map 'all' to 'accurate' (same models)
    mode = 'accurate' if args.mode == 'all' else args.mode

    downloader = ModelDownloader(mode=mode)

    if args.verify_only:
        downloader.verify_all()
    else:
        successful, total = downloader.download_all()

        if successful == total:
            downloader.verify_all()

        sys.exit(0 if successful == total else 1)


if __name__ == '__main__':
    main()
