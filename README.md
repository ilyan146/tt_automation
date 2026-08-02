# TT Automation

A local Streamlit application that extracts telegraphic-transfer details from
invoice images, PDFs, and Excel workbooks, presents the values for review, and fills the
project's fixed legacy Excel template.

## Requirements

- Windows with desktop Microsoft Excel installed
- Python 3.13.12 (managed automatically by `uv` from `.python-version`)
- An OpenAI API key for a model that accepts image and PDF file inputs

Desktop Excel is required because the target template is an old `.xls` workbook.
The app preserves that format and its existing formatting through `xlwings`.

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

Every value in `.env.example` already works against the shared Azure OpenAI endpoint,
so only the key has to be filled in:

```dotenv
OPENAI_API_KEY=your-key-here
```

## Configuration

Settings are read from `.env` by `config.py`. The app starts without a key and warns
until one is set.

| Variable | Default | Notes |
| --- | --- | --- |
| `OPENAI_BASE_URL` | none, required | Azure OpenAI `/openai/v1/` endpoint shipped in `.env.example` |
| `OPENAI_API_KEY` | none | Blank counts as missing; extraction stays disabled |
| `OPENAI_MODEL` | `gpt-5` | Must support image and PDF file inputs |
| `OPENAI_REASONING_EFFORT` | `low` | One of `low`, `medium`, `high` |
| `OPENAI_TIMEOUT_SECONDS` | `90` | Per request |
| `OPENAI_MAX_RETRIES` | `2` | Optional; not listed in `.env.example` |

Start the app:

```powershell
uv run streamlit run src/tt_automation/app.py
```

Open `http://localhost:8501`, upload one or more images, PDFs, or Excel files, review the
extracted values, and generate the completed workbook.

## Supported Sources

| Type | Suffixes | Sent to OpenAI as |
| --- | --- | --- |
| Image | `.jpg`, `.jpeg`, `.png`, `.webp` | Base64 image, high detail |
| PDF | `.pdf` | Base64 file input; every page is read |
| Workbook | `.xls`, `.xlsx`, `.xlsm` | Normalized cell text |

Up to 15 files of 20 MB each per run, extracted concurrently, four at a time. Each file
produces its own review tab and its own workbook.

## Project Layout

```text
src/tt_automation/
	app.py                         Streamlit workflow and review form
	config.py                      .env settings and fixed template path
	models.py                      Shared validated extraction schema
	extraction/
		documents.py                 Upload validation and document kind registry
		workbook_reader.py           Bounded XLS/XLSX/XLSM normalization
		openai_extractor.py          OpenAI structured-output adapter
	excel/
		generator.py                 Download-ready workbook generation
		template_writer.py           Fixed cell mapping and Excel writer
templates/
	telegraphic_transfer_template.xls
tests/
```

The modules have one-way responsibilities: sources are normalized, OpenAI returns
`TransferData`, the user reviews that model, and deterministic code writes the
template. OpenAI never chooses target cells or edits a workbook directly.

## Fixed Cell Mapping

The only target template is `templates/telegraphic_transfer_template.xls`, sheet
`Sheet1 (2)`. The mapping lives in `excel/template_writer.py`:

| Field | Cell |
| --- | --- |
| Transfer date | `L7` |
| Beneficiary name | `E21` |
| Currency and amount | `K21` |
| Beneficiary account | `B25` |
| Beneficiary address | `E28` |
| Beneficiary bank | `E30` |
| Bank country | `L30` |
| SWIFT / BIC | `L32` |
| Bank branch and address | `B33` |
| Payment purpose | `D41` |
| Invoice number | `D42` |
| Invoice date | `D43` |

To add a field later, add it to `TransferData`, update the OpenAI field description,
add it to the review form, and map it in `build_cell_values`.

## Tests

```powershell
uv run pytest -q
```

The tests do not call OpenAI. The OpenAI adapter uses a fake client, while the
template integration test opens a copied workbook through local Excel and reads the
result back with `xlrd`.

## Data Handling

- Uploaded source documents are sent to OpenAI for extraction.
- Uploads and generated workbooks are held in memory or temporary directories.
- The original template is copied before every write and is never modified.
- `.env` is ignored by Git; do not place API keys in source code.
- Document text is treated as untrusted data, never as instructions.
- Modern workbook formulas are read from their last cached values. Open and save a
	source workbook in Excel first if its formulas have not been calculated recently.
