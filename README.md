🛵 Rotagas - Sistema de Gestão Inteligente de Rotas e Vendas

O Rotagas é uma solução SaaS completa, desenhada especificamente para depósitos e distribuidoras de gás. O sistema resolve o caos da logística de rua, automatiza a prospecção comercial e blinda o faturamento contra fraudes e esquecimentos.

🏗️ Arquitetura do Sistema (Os 3 Pilares)

O software foi construído sob um modelo de 3 interfaces distintas, cada uma otimizada para a realidade do seu utilizador:

1. 👑 Painel do Gerente (Gestão & Auditoria)

Focado em inteligência de dados e controle financeiro.

Dashboard em Tempo Real: Visualização do caixa do dia, metas de vendas e tickets médios.

Mesa de Planeamento: Filtros inteligentes para identificar clientes "Atrasados" ou "Virados para a Concorrência".

Relatório de Auditoria: O "Dedo Duro". Monitorização de horários de cliques dos estagiários e localização GPS dos motoqueiros.

Importação de Dados: Motor resiliente para migrar bases de clientes via CSV em segundos.

2. 🎧 Cockpit Comercial (Inside Sales)

Desenhado para alta produtividade (Meta: 400 ligações/dia).

Mailing Ativo: Lista de prospecção baseada em carteiras atribuídas.

Integração WhatsApp: Botão "Click-to-Chat" com mensagens automáticas personalizadas.

Justificativa de Recusa: Pop-up inteligente para captar preços da concorrência e agendar retornos.

Automação Logística: Ao vender por telefone, o sistema gera automaticamente a ordem de entrega no telemóvel do motoqueiro.

3. 🛵 App do Motoqueiro (Logística de Rua)

Interface Mobile-First com botões "Fat-Finger" para uso rápido na rua.

Check-in Geolocalizado: Captura de GPS no momento da chegada para garantir a presença física.

Navegação Inteligente: Integração direta com Google Maps e Waze com um clique.

Baixa Financeira: Registro de recebimentos (Dinheiro, PIX, Cartão) com abate automático na dívida do cliente.

🛠️ Tecnologias Utilizadas

Linguagem: Python 3.x

Framework Web: Django 5.x

Base de Dados: SQLite (Desenvolvimento) / PostgreSQL (Produção)

Frontend: Bootstrap 5 (Customizado com a identidade visual Supergasbras)

Ícones: FontAwesome 6

Gráficos: Chart.js

🚀 Como Executar o Projeto Localmente

Siga os passos abaixo para rodar o Rotagas na sua máquina:

Clone o repositório:

git clone [https://github.com/wagdevce/rotagas.git](https://github.com/wagdevce/rotagas.git)
cd rotagas


Crie e ative o ambiente virtual:

python -m venv venv
# No Windows:
.\venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate


Instale as dependências:

pip install -r requirements.txt


Execute as migrações do banco de dados:

python manage.py migrate


Crie o utilizador administrador:

python manage.py createsuperuser


Inicie o servidor:

python manage.py runserver


Acesse: http://127.0.0.1:8000

🛡️ Segurança e Regras de Negócio

RBAC: Controle de acesso baseado em grupos. Motoqueiros não acedem ao faturamento; Estagiários não acedem ao planeamento.

Anti-Fraude: Registro de timestamps em cada interação comercial para auditoria de produtividade.

Integridade Financeira: Cálculos realizados no backend com Decimal para evitar erros de arredondamento em moedas.

🔮 Próximos Passos (Roadmap)

[ ] Implementação de Mapa de Calor para visualização de densidade de clientes.

[ ] Módulo de Controle de Vasilhames (Cascos).

[ ] Sistema de Comissões Automáticas para motoqueiros e vendedores.

[ ] Dashboard de Previsão de Consumo (IA) para alertar quando o gás do cliente está perto de acabar.

Desenvolvido por WM Soluções Digitais
"Energia que move o seu negócio."