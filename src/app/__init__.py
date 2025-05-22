from .gui import ServerManager

class app_init:
    def __init__(self):
        self.server = ServerManager()
        self.server.mainloop()