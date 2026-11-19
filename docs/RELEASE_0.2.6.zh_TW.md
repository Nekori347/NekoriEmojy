[简体中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.md) | [繁體中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.zh_TW.md) | [English](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.en.md) | [日本語](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.ja.md)

# NekoriEmojy 0.2.6

本次更新著重改善大量表情的搜尋、瀏覽與整理體驗，新增無須重新啟動的資源庫切換，並進一步完善安裝與更新流程。

## 新增功能與改善

- **快速切換資源庫**：現在可以直接在設定中切換不同的本機表情資源庫，無須重新啟動程式。
- **更快的快速面板**：最佳化首次搜尋與縮圖載入，瀏覽大量表情時更加流暢。
- **更穩定的瀏覽位置**：改善分類、搜尋、最近使用及系統匣恢復時的捲動位置記錄，切換檢視後更容易接續原本的位置瀏覽。
- **動態表情顯示**：代表影格與裁切效果在圖庫及快速面板之間保持同步。ANIM 角標改為輕巧的半透明樣式，滑鼠懸停時會自動淡化。

## 問題修正

- 修正最近使用清單在其他頁面傳送表情或調整顯示數量後，可能仍顯示舊內容的問題。
- 修正失效表情重新繫結新檔案後，可能沿用原檔案動態標記的問題。
- 改善資源庫切換及更新視窗的狀態管理。
- 修正部分安裝路徑出現重複目錄的問題。安裝及解除安裝時會檢查正在執行的程式，避免檔案遭到不完整的替換或移除。
- 改善內建更新時的程式結束、失敗復原與重試流程，並加強長時間無回應時的本機診斷記錄。

## 下載與升級

提供 Windows x64 安裝版及免安裝版，OCR 文字辨識仍為選用元件。

使用安裝版升級前，請儲存正在編輯的內容，並從系統匣完整結束舊版程式，再執行安裝程式。透過軟體內建更新時，依畫面提示操作即可。

原有設定與獨立表情資源庫會繼續沿用。

[**Windows 安裝版（推薦）**](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-Setup-0.2.6.exe) · [Windows 免安裝版](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-0.2.6-Windows-Portable.zip)
