FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copia config customizada do Nginx com proxy reverso
COPY nginx.conf /etc/nginx/conf.d/

# Copia apenas os arquivos necessários para produção (exclui arquivos de dev)
COPY index.html /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/
# Nota: test_chat.html, split_css.py, split_js.py NÃO são copiados em produção

EXPOSE 80
