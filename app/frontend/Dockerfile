FROM httpd:2.4

RUN sed -i \
    -e 's/^#LoadModule mpm_event_module/LoadModule mpm_event_module/' \
    /usr/local/apache2/conf/httpd.conf

COPY apache/httpd.conf /usr/local/apache2/conf/httpd.conf

COPY index.html styles.css app.js /usr/local/apache2/htdocs/

EXPOSE 80
