# Spezifikationen

Eine Datei je Vorhaben: `docs/specs/SPEC-<thema>.md`.

## Aufbau

```markdown
# Spezifikation: <Thema>

Stand: JJJJ-MM-TT
Bezug: <andere Specs, Commits, Issues>

## Ziel

<Was danach anders ist, in zwei bis drei Sätzen. Kein Lösungsweg.>

## Entscheidungen

<Je Entscheidung ein Abschnitt: Was gilt, und warum. Die verworfene
Alternative mit dem Grund, warum sie verworfen wurde.>

## Abweichungen

<Beim Umsetzen entstanden? Hier nachziehen, nicht stillschweigend tun.>
```

## Regeln

- **Vor dem Bauen schreiben, nach dem Bauen nachziehen.** Eine Spec, die den
  Code beschreibt, ohne vorher dagewesen zu sein, ist eine Dokumentation und
  gehört ins `HANDBUCH.md`.
- **Nur für Vorhaben über mehrere Sitzungen.** Was in einer Sitzung fertig
  wird, braucht keine Spec — dann genügt ein sauberer Commit.
- **Entscheidungen statt Aufgabenlisten.** Die Spec hält fest, *was gilt*;
  offene Punkte gehören in „Ziel" oder in eine Notiz, nicht als Checkliste,
  die nach zwei Wochen niemand mehr abhakt.
- **Eine Spec, ein Thema.** Lieber zwei Dateien als eine, die zwei Vorhaben
  vermischt.
- **Prüfen gegen die Spec.** Beim Review wird der Diff gegen diese Datei
  gehalten: Erfüllt er das Ziel, und tut er nichts, was hier nicht steht?
