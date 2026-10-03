"""Sorgt dafür, dass die Testdateien niemals die echte Datenbank anfassen.

⚠️ Diese Datei muss VOR dem Import von 'main' importiert werden:

    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    import testkonfiguration  # noqa: F401  - muss vor 'main' stehen

Der Grund: Der SQLAlchemy-Engine wird beim Import von 'main' erzeugt und liest
den Pfad aus APP_DATA_DIR. Die Testdateien setzten früher in setUp
`SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'` - das hat aber keine Wirkung,
weil der Engine zu diesem Zeitpunkt längst steht. Nachgemessen:

    Engine-URL nach Import : sqlite:////.../data/gefahrstoffe.db
    Engine-URL nach setUp  : sqlite:////.../data/gefahrstoffe.db

In der Folge liefen `db.create_all()` und vor allem `db.drop_all()` aus
tearDown gegen die echte data/gefahrstoffe.db und löschten dort nach jedem
Testlauf alle Tabellen. Hier wird APP_DATA_DIR deshalb auf ein frisches
Verzeichnis unter /tmp gesetzt, bevor 'main' importiert wird.
"""
import os
import tempfile

# Bewusst kein setdefault: ein bereits gesetzter APP_DATA_DIR darf nicht dazu
# führen, dass die Tests gegen echte Daten laufen und deren Tabellen löschen.
os.environ['APP_DATA_DIR'] = tempfile.mkdtemp(prefix='gsv-test-')
