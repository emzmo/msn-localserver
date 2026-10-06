import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
db.Base.metadata.create_all(db.engine)
print('t_mail table ensured')