[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

# NekoriEmojy

A local sticker manager for Windows.

Collect, organize, find, and send stickers. Alongside categories, tags, and search, the aim is to make everyday tasks more direct: drag the stickers you see to organize them, and reach common actions without going through several menus.

<!-- Publication production: replace the image below with a real screenshot from the isolated demo library. Temporarily render visible natural-language UI text in Sarkaz glyphs. Do not include the font, conversion code, or demo database in release packages. Show the Endfield subcategory with four leading stickers, the collapsible Chen Qianyu category node, then the remaining directly contained stickers. Do not turn the source folder “表情” into a category. -->

<p align="center">
  <img src="docs/media/hero.png" alt="NekoriEmojy main panel: categories, subcategories, category nodes interleaved with stickers, and the tag panel" width="100%">
</p>

[**Download the latest version**](https://github.com/Nekori347/NekoriEmojy/releases/tag/v0.2.1) · [**Report an issue**](https://github.com/Nekori347/NekoriEmojy/issues) · [**Feature overview**](#features)

---

<a id="features"></a>
## Feature overview

- [🗂️ **Categories, subcategories, and nodes**](#organization) — Category levels, top category tabs, and collapsible, reorderable category nodes within the content area.
- [↕️ **Drag and arrange freely**](#drag-and-sort) — Reorder one or several stickers together, and arrange category nodes alongside them.
- [🔎 **Find and preview**](#find-and-preview) — Names, tags, optional text recognition, recently used stickers, and GIF thumbnail frames.
- [⚡ **Quick use**](#quick-use) — Paste to import, click to send, drag to send, and the quick panel.
- [🎨 **Appearance and personalization**](#appearance) — Light and dark themes, live accent color adjustment, flexible layouts, a custom app icon, and a multilingual interface.
- [📦 **Import and data management**](#import-and-data) — A separate sticker library, Suzu data migration, native resource packages, compatible sharing packages, and settings backups.

---

<a id="organization"></a>
## 🗂️ Categories, subcategories, and nodes

Categories are more than a column of folders on the left. NekoriEmojy uses a single category hierarchy, presenting different levels in the **left category sidebar, top category tabs, and sticker content area** according to your current location. You can enter a subcategory from a parent category, or organize the next level of content directly in the current view.

**Category nodes can be interleaved with ordinary stickers.** A node can come after several stickers, with more ordinary stickers following it. Nodes can be expanded, collapsed, and reordered. They are neither directory shortcuts restricted to the top of the list nor separators unrelated to the content.

This helps divide a large collection into groups by character, purpose, or your own habits: expand a group when needed and collapse it otherwise, without creating a separate browsing page for every small group.

<p align="center">
  <img src="docs/media/category-node.png" alt="Mixed arrangement within a subcategory: stickers appear before and after a node, which expands to show its contents" width="100%">
</p>

<p align="center">
  <img src="docs/media/category-node-demo.gif" alt="Actual operation: entering a subcategory from its parent, then expanding and collapsing a node" width="82%">
</p>

> **Categories, category nodes, and tags are different concepts.** Categories and nodes belong to the same hierarchy. Top category tabs switch between category views at the current location; sticker tags provide a separate way to associate and find stickers. A sticker can also belong to multiple categories without storing duplicate image files.

<a id="drag-and-sort"></a>
## ↕️ Drag and arrange freely

Organize stickers directly where they appear whenever possible.

- Drag a single sticker to change its position, or **select several and drag them together to reorder them**.
- Drag stickers onto supported category or node target areas to organize them using the corresponding action.
- Move category nodes within a category view to interleave nodes and ordinary stickers in your preferred order.
- Adjust the category hierarchy and sibling order as needed, without relying solely on a separate management dialog.
- Use the tag panel and batch operations to avoid repeating the same changes one sticker at a time.

Besides pasting through a shortcut or button, you can right-click at a chosen position in the content area and paste new stickers directly into the place you are organizing.

The demonstration below focuses on **moving several stickers and collapsible nodes within the same content view to change the browsing order directly**, rather than simply dragging files into folders.

<p align="center">
  <img src="docs/media/drag-sort-demo.gif" alt="Reordering selected stickers and moving a category node while retaining ordinary stickers before and after it" width="82%">
</p>

---

<a id="find-and-preview"></a>
## 🔎 Find and preview

As a collection grows, recognizing and finding the sticker you want matters more than simply saving it.

- **Search by name and tag**: narrow results using existing names, tags, and keywords.
- **Text recognition (OCR)**: install the local component when needed to recognize text in stickers and make it searchable. Recognized text and manual tags are stored separately.
- **Recently used**: return to recent stickers from the main panel or quick panel.
- **Animated previews**: view the actual animation of GIFs and other animated stickers.
- **Custom GIF thumbnail frame**: choose a more recognizable frame for the list thumbnail without modifying the original animation.

That last option is particularly useful when the default GIF thumbnail is blank or shows a transitional frame. Choose a clearer image so that a saved sticker remains easy to recognize in the list.

<p align="center">
  <img src="docs/media/search-demo.gif" alt="Finding stickers by name, tags, or recognized text" width="82%">
</p>

<p align="center">
  <img src="docs/media/gif-frame-compare.png" alt="The same GIF with its default thumbnail frame and a custom frame" width="100%">
</p>

---

<a id="quick-use"></a>
## ⚡ Quick use

You do not need to open the full management interface every time.

- **Click to send**: click a sticker to carry out the sending process in a supported target window, without manually switching back and pasting each time.
- **Drag to send**: drag a sticker to the desired location in the target application.
- **Paste to import**: copy an image, then add it to the library using the interface button.
- **Quick panel**: invoke a compact panel through a shortcut to search for stickers or choose recently used ones.

In the main gallery, you can configure a single click to select a sticker or send it directly, according to your preference.

Sending still depends on how the target application accepts images and on the current window state in Windows. For incompatible targets, use ordinary copy and paste or another conventional method.

**Send static stickers as GIFs**

Some chat applications display ordinary static images as large, full-size pictures.

NekoriEmojy offers a “Convert static images to GIF when sending” option. It temporarily converts a static sticker to a single-frame GIF when sending, in an attempt to display it in a form better suited to stickers.

This does not animate a still image or modify the original image stored in your library. The actual appearance still depends on the chat application receiving the image.

<p align="center">
  <img src="docs/media/send-as-gif.png" alt="Setting to convert static images to GIF when sending" width="65%">
</p>

<p align="center">
  <img src="docs/media/quick-panel.png" alt="The quick panel and recently used stickers" width="60%">
</p>

<p align="center">
  <img src="docs/media/quick-use-demo.gif" alt="Actual operation: pasting to import, quickly finding a sticker, and clicking to send" width="82%">
</p>

---

<a id="appearance"></a>
## 🎨 Appearance and personalization

You can also adjust the interface to suit the way you use it.

- Different category sidebar display modes and ways to browse subcategories and the content area.
- Combinations of top category tabs, collapsible nodes, and the tag panel.
- Layout options such as the tag panel's position and expanded state, and sticker thumbnail size.
- Light and dark themes and window appearance settings.
- A **custom app icon** to change how the app is identified in its windows, the taskbar, and the system tray.
- An **internationalized (i18n) interface** and customizable keyboard shortcuts.

The main panel is for organization and management; the quick panel offers a more compact way to find and send stickers day to day. Both share the same sticker data.

### Themes and accent colors

NekoriEmojy supports light, dark, and system appearance modes, and lets you choose your own theme accent color.

The interface previews accent color changes live. You do not need to save and return to the main window each time to see the result. If you are not satisfied, you can cancel or discard your changes, then save once you are happy with them.

Both light and dark themes can be used with different accent colors.

<p align="center">
  <img src="docs/media/theme-light-dark.png" alt="Light and dark themes" width="100%">
</p>

<p align="center">
  <img src="docs/media/theme-accent-live.gif" alt="Live interface preview while adjusting the theme accent color" width="82%">
</p>

### Custom app icon

In addition to changing interface colors, you can replace NekoriEmojy's own app icon.

Choose a local image or use an image from your sticker library directly. Applying it updates the icons in the app window, taskbar, and system tray. You can restore the default icon when needed.

<p align="center">
  <img src="docs/media/custom-app-icon.png" alt="Using a sticker as the app icon, showing its appearance in the window, taskbar, and system tray" width="80%">
</p>

---

<a id="import-and-data"></a>
## 📦 Import and data management

Alongside everyday collecting and organizing, there are tools for maintaining your library:

- Import images from local files, folders, or the clipboard.
- Import and export sticker collections for organization and sharing.
- Manage multiple selections, change category associations, and reorder items.
- Import tools for sources such as QQ and Telegram, and ways to migrate existing sticker data from SuzuEmojy.
- Install the optional text recognition component and manage recognition tasks.
- Find similar images: scan the library for similar images, preview them together, and choose for yourself what to organize.

Conditions vary by source and format. If something is unsupported, refer to the messages shown in the application.

### A separate sticker library directory

NekoriEmojy's sticker library does not have to be in the same folder as the program.

Choose where to store it, such as another drive or a directory dedicated to your image collection. Imported sticker files, category information, and the resource index are stored in the selected library; personal app settings are stored separately.

Changing the installation location or reinstalling the program does not mean you must reorganize the entire collection. As long as the original library is intact, you can reconnect to it in settings.

After selecting a different library, you must save settings and restart the app to switch to it. When importing stickers, the app copies or converts images into the selected library rather than directly managing the original source files.

This also makes it easier to back up or move the library separately, or store it somewhere more suitable.

<p align="center">
  <img src="docs/media/external-library.png" alt="A separate sticker library directory and settings for reconnecting to it" width="80%">
</p>

### Resource packages, sharing, and backups

You can also export an organized library for safekeeping.

NekoriEmojy provides several kinds of data export for different purposes:

**Nekori native resource packages**

Export the current sticker library as a ZIP resource package. Along with sticker images, it preserves category and subcategory structure, category icons, the order of nodes and stickers, tags, recognized text, selected GIF thumbnail frames, and other related information already recorded in the library.

Native resource packages are suitable for saving and transferring the way you have organized stickers in Nekori. Importing merges their data into the current library rather than overwriting the entire existing library.

<p align="center">
  <img src="docs/media/nekori-package.png" alt="Nekori native resource package import and export, with an actual ZIP file" width="75%">
</p>

**Compatible sharing packages**

You can also export sticker sharing packages in Suzu format, for either the entire library or a selected category, to organize and share images in a compatible format.

Larger sharing packages can be split into multiple archives by size for storage or transfer.

Package formats do not preserve exactly the same information. If your main goal is to retain organization such as the mixed order of nodes and stickers in Nekori, prefer the Nekori native resource format.

**Settings files**

App settings can be exported separately as a JSON file and imported again when needed.

This lets you save your interface and interaction preferences separately from the sticker data you organize.

<p align="center">
  <img src="docs/media/data-export.png" alt="Exporting native resource packages, compatible sharing packages, and settings files" width="80%">
</p>

**Full data backups**

The sticker library directory and app settings are stored separately. For a full backup, also save the actual library directory and necessary app data, rather than keeping only a sharing package.

Resource packages are for exporting, migrating, and sharing your organization work; a full directory backup preserves the original library state. Use both as needed.

### Migrating from SuzuEmojy

If you previously used SuzuEmojy, NekoriEmojy's migration tools let you continue using your existing sticker collection.

Two sources are currently supported:

- **Read existing SuzuEmojy data:** find a running SuzuEmojy instance on this computer, read its existing data, and migrate it into Nekori.
- **Import a Suzu sharing package:** select a previously exported sticker resource archive to import.

Migration attempts to preserve the images, categories, subcategories, category icons, tag keywords, and ordering information it can read. Your original Suzu data remains unchanged; you do not need to delete the old app first.

What can actually be preserved depends on the data included in the source, since sources and formats can differ. After migration, check the categories, sticker counts, and order.

This compatibility feature is primarily intended to reduce repeated importing and reorganization when changing apps.

<p align="center">
  <img src="docs/media/suzu-migration.png" alt="Entry points for migration from SuzuEmojy" width="65%">
</p>

---

<a id="download"></a>
## Download and use

Get the latest version from [GitHub Releases](https://github.com/Nekori347/NekoriEmojy/releases/tag/v0.2.1).

Two options are currently prepared for Windows x64:

- **Installer**: install the app using the installer.
- **Portable package**: extract it and follow the instructions inside, if you prefer not to use an installer.

Text recognition is an **optional component**. Ordinary organization, search by name and tag, and sending do not require it. If you need to recognize text in images, follow the installation prompts in app settings.

Keyboard shortcuts and some interface behaviors can be viewed and adjusted in settings.

**Updates and data:** the sticker library and personal configuration may be stored in different locations. Back up both before updating or changing the installation method. Uninstalling the app or deleting its program directory is not the same as cleaning up user data. Refer to the Release notes for the relevant version.

---

<a id="development"></a>
## About development

NekoriEmojy is a personally maintained **Vibe Coding project**. Feature planning, interface design, and interaction changes mainly follow personal needs; code is largely written, modified, and iterated with AI assistance.

There may still be undiscovered bugs, especially differences in dragging and sending across applications or behavior in different Windows environments. Reproducible bug reports and suggestions are welcome through [GitHub Issues](https://github.com/Nekori347/NekoriEmojy/issues).

---

## Open source and acknowledgments

**SuzuEmojy**

NekoriEmojy is built on the open-source code of [SuzuEmojy](https://github.com/IxinorTyan/SuzuEmojy) by IxinorTyan. Work on that foundation includes changes to sticker library data organization, category and node interactions, interface layout, and other everyday details.

Thank you to the original author for making the source available, and to the authors of related open-source projects and third-party components.

The original SuzuEmojy project is licensed under GPL-3.0. The repository's LICENSE and related license files govern the specific licensing of this project and its third-party code and resources.

Some publication screenshots use community-recreated glyphs from [Endfield_Font](https://github.com/lhclbt/Endfield_Font) as temporary display text (author: lhclbt / 罗醭坦; [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)). The font is not bundled as a resource in the official NekoriEmojy app.

For specific licenses, attribution, and scope of use for the project and its third-party components, see [LICENSE](LICENSE) and the related license files in the repository.

---

*This is a personal tool that is still being improved. Descriptions and demonstrations are based on the actual features of the corresponding release.*
