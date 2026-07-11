# Edetachy ASAP, Greek

**Greek, ASAP.**

Edetachy is a deliberately small vocabulary tool for moving learners into primary texts before they feel fully ready.

The name comes from a recurring urgency formula in the Greek Magical Papyri:

> **ἤδη, ἤδη, ταχύ, ταχύ**  
> **今すぐ、今すぐ。**  
> “Now, now - quickly, quickly.”

A well-known example occurs in **PGM I 247-262**, an invisibility procedure. The phrase presses for immediate action. That suits the teaching idea behind Edetachy:

> **The goal is not mastery. The goal is autonomy. Get there ASAP.**

## What it does

- Vocabulary, aorist, and participle modules
- Up to 20 new cards per learning session
- Three states:
  - **I know it**
  - **Looks familiar**
  - **I don't know**
- Review mode shows only **Looks familiar**
- User registration with a 4-digit PIN
- Teacher view of student progress
- CSV replacement: importing a new CSV overwrites the current deck and resets that category's progress
- Progress reset controls
- Full-list and known-only PDF exports
- Japanese and English interface
- SQLite storage

## First launch

```bash
pip install -r requirements.txt
streamlit run app.py
```

On macOS, you can also double-click `start.command`.

The default teacher registration code is:

```text
edetachy
```

For deployment, set a different environment variable:

```text
EDETACHY_TEACHER_CODE
```

## CSV formats

### Vocabulary

```csv
rank,greek,meaning,hint
1,λόγος,言葉・ロゴス,logic（論理）
```

### Aorist

```csv
rank,present,aorist,meaning
1,λέγω,εἶπον,言う
```

### Participles

```csv
rank,present,present_participle,aorist_participle,meaning
1,λέγω,λέγων,εἰπών,言う
```

All CSV files should be UTF-8. Files exported by spreadsheet software as UTF-8 CSV are supported.

## Data policy

This first version is intentionally low-stakes. It stores display names, hashed PINs, decks, and progress in a local SQLite file. On temporary hosting, the database may disappear when the application restarts. For the initial classroom trial, that is acceptable: lost progress simply becomes review.

## Source note

For the phrase **ἤδη, ἤδη, ταχύ, ταχύ**, see PGM I 247-262 and studies of temporal urgency formulas in the Greek Magical Papyri.

## License

MIT

## 管理者モード

管理者は教師モードの全機能に加え、登録済みの学習者・教師・他の管理者を削除できます。削除すると該当ユーザーの学習履歴も削除されます。自分自身は削除できません。

管理者登録コードは環境変数 `EDETACHY_ADMIN_CODE` で設定します。未設定時のα版初期値は `edetachy-admin` です。公開時には必ず変更してください。

### AI教材用テキスト

教師モードでは、学習者・カテゴリ・ステータスを選び、該当する語彙や語形をコピー用テキストボックスへ直接出力できます。全学習者に共通する項目の抽出と、AI向け練習問題作成指示文の付加にも対応しています。
