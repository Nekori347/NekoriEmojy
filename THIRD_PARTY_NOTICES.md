# NekoriEmojy — sources and third-party notices

NekoriEmojy is a GPL-3.0 fork of SuzuEmojy v1.13.0 (IxinorTyan), commit
0152f075a5595f12cf71512321b84fa76755820e. Original copyright and LICENSE remain.
Upstream source: https://github.com/IxinorTyan/SuzuEmojy
Nekori source: https://github.com/Nekori347/NekoriEmojy
The exact local build commit is recorded in BUILD_INFO.json. Corresponding local
application source is preserved with this build; unpublished local changes are
not asserted to be available from the public repository.

The lightweight distribution installs the dependencies listed in requirements.txt
into a user runtime. Their own license files remain in their distributions.
Principal components include PySide6/Shiboken (LGPL/GPL options),
PySide6-Fluent-Widgets (GPL-3.0), PySideSix-Frameless-Window (LGPL-3.0),
Pillow, requests, pynput, keyboard, certifi, rlottie-python, pypinyin and OpenCC.
Consult installed package metadata and bundled source notices for exact versions
and terms. A dependency is not relicensed by inclusion in Nekori.

UI resources include Tabler Icons (MIT), Sarasa UI SC (SIL OFL),
Rajdhani (SIL OFL), and JetBrains Mono (SIL OFL). Their existing resource notices
and license files are retained in fluent_ui/assets. Sticker images belong to their
original creators; personal libraries and test images are never distributed.

OCR is optional and is not included in the base application. Its separate package
retains its own RapidOCR, ONNX Runtime and model notices.
