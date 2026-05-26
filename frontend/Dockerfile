FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config (if you want SPA fallback, you can adjust)
COPY nginx.conf /etc/nginx/conf.d

# Copy static site files
COPY . /usr/share/nginx/html

EXPOSE 80
