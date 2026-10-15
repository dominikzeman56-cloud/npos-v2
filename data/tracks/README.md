# Tracky

Jeden adresář na analyzovaný track: `<id>/meta.json`, `<id>/analysis.json` (podle `core/track-analysis.schema.json`), volitelně `<id>/build-sheet.json` a `<id>/notes.md`.

Pravidla: cizí track musí mít záznam v `knowledge/sources.jsonl` (`source_id`); každé pole analýzy nese `confidence` a `basis`; basová modulace z plného mixu je nejvýš `hypothesis`. Poznámky „po sluchu" k trackům, jejichž existenci nelze ověřit, se sem nezapisují.
