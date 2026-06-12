# AI潜水艦ハンター

オープンラボ向けのPygame展示アプリです。

人間プレイヤーとAIが同じ海域マップに対して交互に爆撃し，潜水艦の直撃数と撃沈ボーナスで得点を競います。  
AIは，これまでの爆撃結果から潜水艦配置の候補を絞り込み，各マスの潜水艦存在確率と期待情報量を計算して爆撃地点を選びます。

## 1. uvの準備

このプロジェクトでは，Pythonの環境管理に `uv` を使用します。  
### uvのインストール（必要な場合）
- macOS または Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Windows の PowerShell の場合
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 日本語フォントのインストール

Linux環境での実行に必要です。
```bash
sudo apt update
sudo apt install -y fonts-takao fonts-noto-cjk
sudo locale-gen ja_JP.UTF-8
```
インストール後，ターミナルを開き直してから，以下に進んでください。


## 2. 実行方法

プロジェクトのフォルダに移動します。
```bash
cd submarine_hunter_pygame
```
依存ライブラリをインストールします。
```bash
uv sync
```
ゲームを実行します。
```bash
uv run python -m submarine_hunter
```
