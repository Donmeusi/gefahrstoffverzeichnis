def check_zusammenlagerung(lgk1: str, lgk2: str):
    """
    Überprüft die Zusammenlagerung nach TRGS 510.
    Gibt ein Tuple zurück: (Erlaubt: bool, Warnmeldung: str)
    
    Diese Matrix ist eine vereinfachte Version zur Veranschaulichung der wichtigsten
    Zusammenlagerungsverbote. (Vollständige Matrix siehe TRGS 510 Anlage 1).
    """
    if not lgk1 or not lgk2:
        return True, ""
        
    lgk1 = str(lgk1).strip().upper()
    lgk2 = str(lgk2).strip().upper()
    
    if lgk1 == lgk2:
        return True, ""

    # LGK 1: Explosivstoffe -> Generell verboten mit allem
    if lgk1 == "1" or lgk2 == "1":
        return False, "Explosivstoffe (LGK 1) müssen separat gelagert werden."
        
    # LGK 6.2: Ansteckungsgefährliche Stoffe -> Separat lagern
    if lgk1 == "6.2" or lgk2 == "6.2":
        return False, "Ansteckungsgefährliche Stoffe (LGK 6.2) müssen separat gelagert werden."

    # LGK 7: Radioaktive Stoffe -> Separat lagern
    if lgk1 == "7" or lgk2 == "7":
        return False, "Radioaktive Stoffe (LGK 7) müssen separat gelagert werden."

    # LGK 3 (Entzündbare Flüssigkeiten) und LGK 4.1A / 4.1B / 4.2 / 4.3 / 5.1A / 5.1B / 5.1C / 5.2 / 6.1A / 6.1B / 8A
    # Vereinfachte Verbote:
    
    # 4.1A, 4.2, 4.3 (entzündbar fest, selbstentzündlich, reaktiv mit Wasser) vs. 3 (entzündbar flüssig) -> oft verboten
    if (lgk1 == "3" and lgk2 in ["4.1A", "4.2", "4.3"]) or (lgk2 == "3" and lgk1 in ["4.1A", "4.2", "4.3"]):
        return False, f"Zusammenlagerung von LGK {lgk1} und LGK {lgk2} ist verboten (Brand-/Reaktionsgefahr)."

    # 4.1A, 4.2, 4.3 vs. 5.1A, 5.1B, 5.1C (brandfördernd)
    if (lgk1 in ["4.1A", "4.2", "4.3"] and lgk2.startswith("5.")) or (lgk2 in ["4.1A", "4.2", "4.3"] and lgk1.startswith("5.")):
        return False, f"Zusammenlagerung von entzündbaren/reaktiven Feststoffen (LGK {lgk1}) mit brandfördernden Stoffen (LGK {lgk2}) ist verboten."

    # 5.1A, 5.1B, 5.1C, 5.2 vs. 3 (entzündbare Flüssigkeiten)
    if (lgk1 == "3" and lgk2.startswith("5.")) or (lgk2 == "3" and lgk1.startswith("5.")):
        return False, f"Zusammenlagerung von entzündbaren Flüssigkeiten (LGK 3) und brandfördernden Stoffen (LGK {lgk1 if lgk1.startswith('5') else lgk2}) ist verboten."

    # Säuren (oft in 8B oder 8A) und Basen (oft auch in 8A/8B) - hier in der TRGS 510 oft als "Separat lagern" markiert,
    # Wir nehmen hier mal eine allgemeine Warnung für LGK 8 vs. LGK 4.2, 4.3
    if (lgk1.startswith("8") and lgk2 in ["4.2", "4.3"]) or (lgk2.startswith("8") and lgk1 in ["4.2", "4.3"]):
        return False, f"Ätzende Stoffe (LGK {lgk1 if lgk1.startswith('8') else lgk2}) dürfen nicht mit LGK {lgk2 if lgk1.startswith('8') else lgk1} gelagert werden."

    # 6.1A/6.1B vs 3
    if (lgk1 == "3" and lgk2 in ["6.1A", "6.1B"]) or (lgk2 == "3" and lgk1 in ["6.1A", "6.1B"]):
        # Oft eingeschränkt, wir lassen es hier zur Demonstration durch, oder als Warnung
        pass

    # Standardmäßig (wenn keine Regel zuschlägt, vor allem für LGK 10-13)
    return True, ""
