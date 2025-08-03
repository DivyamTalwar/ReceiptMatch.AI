import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ui.pages import ReceiptReconciliationApp

if __name__ == "__main__":
    app = ReceiptReconciliationApp()
    app.run()
