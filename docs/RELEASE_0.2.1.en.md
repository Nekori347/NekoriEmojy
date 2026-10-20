[简体中文](RELEASE_0.2.1.md) | [English](RELEASE_0.2.1.en.md) | [日本語](RELEASE_0.2.1.ja.md)

# NekoriEmojy 0.2.1

NekoriEmojy is a local sticker manager for Windows, with categories and nodes for organization, search, a quick panel, and direct sending.

This release provides an installer and a portable package, along with a text recognition component for those who need it.

## Main features

- **Categories and nodes**: multiple category levels, subcategories, top category tabs, and collapsible nodes that can be interleaved with ordinary stickers.
- **Flexible organization**: drag to reorder one or several stickers, adjust categories, and manage tags.
- **Find stickers**: search by name and tag, recently used stickers, animated previews, and custom GIF thumbnail frames; install the text recognition (OCR) component when needed.
- **Quick use**: the quick panel, paste to import, click to send, and drag to send. You can also choose to send static stickers as single-frame GIFs.
- **Appearance and personalization:** light and dark themes, live theme accent color previews, a custom app icon, adjustable interface layouts, and a multilingual interface.
- **Import and data management:** separate sticker library storage, Nekori native resource package import and export, Suzu-compatible sharing packages, settings file backups, and migration of collections from existing SuzuEmojy data or sharing packages.

See the repository's README for more screenshots and demonstrations.

## Downloads

Choose the appropriate file under **Assets** below:

- **Installer**: run the installer to install the app.
- **Portable package**: extract it and follow the included instructions to launch it.
- **Optional OCR component**: install it only if you need to recognize text in sticker images. Ordinary sticker management does not depend on it.
- **Source code**: for those who want to read the code or build the project themselves.

Use the actual filenames and descriptions in Assets at publication time. Take care to distinguish the installer, portable package, and OCR component package.

## Updates and personal data

Back up your sticker library and personal configuration before upgrading, especially when migrating from an older version or another sticker manager. The library and configuration directories may differ. Do not update the app by directly deleting user data directories.

## Known limitations

- Currently intended primarily for Windows x64.
- The main program uses a build target intended for general x64 use, but has not yet been verified on actual hardware without AVX2 support.
- Text recognition is an optional component that requires additional files on first use. Public download locations depend on the assets actually uploaded with this Release.
- Sending and dragging stickers may behave differently depending on how the target application receives them.

## Feedback and development

This is a personally maintained **Vibe Coding project**, with code largely written and iterated with AI assistance. When reporting a problem through the repository's Issues, please include the app version, steps to reproduce it, and relevant error messages whenever possible.

The project builds on open-source projects including [SuzuEmojy](https://github.com/IxinorTyan/SuzuEmojy). See the repository's README and LICENSE for further source and licensing information.
