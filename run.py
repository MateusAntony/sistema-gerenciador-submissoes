from app import create_app

app = create_app()

if __name__ == '__main__':
    # O servidor embutido do Flask só liga o debugger em desenvolvimento; o comando
    # do contêiner é um servidor WSGI de produção (ver Dockerfile). Risco R5.
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config['APP_ENV'] == 'development',
    )
