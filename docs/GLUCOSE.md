# Glucose

The page reads sensor readings via LibreLinkUp (follower account) and displays a chart, a 48‑hour average, and a record history. The manual insulin log allows editing and deleting.

**This is not a medical device.** It does not replace a doctor or certified equipment. Do not use values from this project to decide doses.

## The calculator comes disabled

The repository **does not provide any dose values**. To enable it, your doctor defines the regimen and you write it to `~/.config/odysseus-kit/config.json`:

```json
"glucose": {
  "fiasp_start": 0,
  "fiasp_base": 0,
  "fiasp_step": 0,
  "carb_per_unit": 0,
  "max_dose": 0,
  "hypo": 70,
  "basal_default": 0,
  "basal_high_avg": 0,
  "basal_low_avg": 0,
  "basal_step": 0
}
```

(Replace the zeros with your doctor's values.) The field names reflect a rapid‑insulin regimen with glucose correction and a carbohydrate‑per‑unit ratio, plus a suggested basal dose adjustment based on a 2‑day average. If not all fields in a block are filled, the block remains disabled.

- The suggestion is always for **you to confirm**; nothing is sent to any device.
- Below the `hypo` threshold the page refuses to suggest insulin.
- The carbohydrate‑by‑photo estimate is approximate; always verify the values.
