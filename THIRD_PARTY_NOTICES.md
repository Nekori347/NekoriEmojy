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

UI icon additions (post-0.2.1): approved Tabler Outline candidates retain the
MIT notice in fluent_ui/assets/icons/LICENSE. mood-plus, tag-plus, menu-order,
clock-up/down and mirrored playlist-add originate at Tabler commit
a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d; list-tree-stroke-2.25 is a local stroke-only derivative.
photo-circle.svg: same Tabler commit, blob 420f6b7ef028abd96e4f79ce9c2ab191d5849830.
Phosphor Regular sticker.svg (unchanged filled outline): phosphor-icons/core
commit 2b75f3ad12b420c9504ef05df8d2564a28f8500e, blob 0c6fbc26bd53018f2e7afd8cd75283f3c07ebcb9.
Source: https://github.com/phosphor-icons/core/tree/2b75f3ad12b420c9504ef05df8d2564a28f8500e
MIT license retained in fluent_ui/assets/icons/LICENSE-Phosphor.
