# NPOS — Pipeline znalostí

Jak se z cizího zdroje stane poznatek v kánonu. Nahrazuje `PHASE_0_KNOWLEDGE_SYNC.md` (ten předpokládal „intake před nástroji" a GitHub Issues jako inbox; nástroje a kánon mezitím vznikly, takže zbývá jen pravidlo toku).

## Vrstvy (viz BLUEPRINT kap. 2)

`0 surový zdroj → 1 destilace (vault 60 Rozbory) → 2 kánon (vault 10–50, 70–80 a knowledge/) → 3 data a nástroje`

## Kroky

1. **Zdroj dorazí** (kurz, video, projekt `.als`, track, podcast, preset pack). Surový materiál zůstává lokálně; do repa nikdy.
2. **Registr zdrojů.** Vznikne záznam v `knowledge/sources.jsonl` podle `core/source.schema.json`: `id`, `kind`, `title`, `verified_by`, `verified_on` (+ `access`, `redistribution`, `vault_note`). **Bez ověření (soubor na disku, přepis, web s URL, projektový soubor, vlastní práce) záznam nevznikne a zdroj se nepoužije.**
3. **Destilace (vrstva 1).** Jeden zdroj = jeden rozbor ve vaultu, vlastními slovy, česky. Každé tvrzení nese `confidence` a `basis`. Nic se nepřepisuje beze změny z cizí práce.
4. **Extrakce kandidátů.** Z rozboru se vytáhnou kandidáti na pravidla (pracovní soubor `Extrakce pro šablonu`, v repu `knowledge/principles/candidates.md`). Kandidát má stav `candidate`.
5. **Povýšení do kánonu** má podmínky (kap. níže). Teprve pak vznikne principy/archetyp/profil se stavem `canon`, `conditional` nebo `school`.
6. **Datová vrstva.** Změřené a ověřené hodnoty se zapisují do `data/tracks/<id>/analysis.json` a `data/presets/<id>.json`; korpus se z nich generuje.
7. **Kontrola.** `python tools/check_repo.py` — frontmatter, odkazy na zdroje, schéma registru.

## Podmínky povýšení

| Cíl | Podmínka |
|---|---|
| `canon` / `consensus` | ≥ 3 nezávislé zdroje se shodou, nebo 2 + vlastní ověření v tracku |
| `conditional` | pravidlo platí v daném kontextu (žánr, tempo, typ zvuku); kontext se napíše |
| `school` | metoda jednoho producenta nebo školy; označí se kdo |
| `dogma_unverified` | jeden zdroj, nebo zdroj z jiného žánru; nezapisuje se jako pravidlo, jen jako položka k ověření |
| `deprecated` | důkaz proti; pravidlo se nemaže, zůstane s odkazem na důkaz |

## Pravidlo pravdivosti

- Žádný odkaz na track, producenta ani číslo bez záznamu v registru.
- Neověřená existence = nezapsáno. (`hypothesis` je štítek pro *výklad*, ne pro *existenci*.)
- Čísla z plného mixu pro basové pásmo jsou nejvýš `hypothesis`.
- Hodnoty z jiného žánru (např. funk-break v10 šablona) se nepřenášejí jako neurofunk standard.

## Co se nesmí

- Nahrát placené video/přepis/PDF do repa nebo do sdíleného exportu.
- Generovat profily producentů ze šablony („vyplň jméno, doplň reference"). Profil má jen to, co je ve vaultu doložené.
- Povýšit pravidlo z jednoho zdroje na kánon.
