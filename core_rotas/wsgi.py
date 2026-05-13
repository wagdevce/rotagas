import os
from django.core.wsgi import get_wsgi_application

# Este ficheiro é a ponte entre o servidor web e a tua aplicação Django.
# O caminho abaixo deve corresponder ao nome da tua pasta de definições.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_rotas.settings')

application = get_wsgi_application()

# OBRIGATÓRIO PARA A VERCEL:
# A Vercel procura uma variável chamada 'app' para iniciar o servidor.
app = application