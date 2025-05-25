from games import bridge


import configparser
def load_config(path='config.txt'):
    config = configparser.ConfigParser()
    config.read(path)
    settings = config['DEFAULT']
    return {
        'isSignature': settings.getboolean('isSignature'),
        'encryption': settings.getboolean('encryption'),
        'hashChain': settings.getboolean('hashChain'),
        'autoPlay': settings.getboolean('autoPlay'),
        'schuffleCheat': settings.getboolean('schuffleCheat'),
        'playCheat': settings.getboolean('playCheat'),
        'serverHost': settings.get('serverHost'),
        'serverPort': settings.getint('serverPort'),
    }

def main():
    cfg = load_config()
    p2pInterface = client.p2pInterface(isSignature=cfg['isSignature'], serverHost=cfg['serverHost'], serverPort=cfg['serverPort'])
    bridge = Bridge(
        p2pInterface=p2pInterface,
        encryption=cfg['encryption'],
        schuffleCheat=cfg['schuffleCheat'],
        playCheat=cfg['playCheat'],
        hashChain = cfg['hashChain'],
    )
    bridge.run()
if __name__ == "__main__":
    bridge.main()