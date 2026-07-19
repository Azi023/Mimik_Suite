"""Free-Gemini VISION: image understanding for brand memory (study, palette, voice).

Image *understanding* is free-tier; only image *generation* needs billing — so this
package is on the free path, same key as the TEXT client.
"""

from .gemini_vision import generate_vision
from .study import CreativeStudyError, study_creative

__all__ = ["generate_vision", "study_creative", "CreativeStudyError"]
