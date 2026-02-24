"""Módulo experimental para scraping con Selenium.

Actualmente es un prototipo simple que arranca un `webdriver`. Mantener deshabilitado
en entornos de producción y tests.
"""

from selenium import webdriver


def ingresar(url):
    """Prototype: abre una URL con Firefox webdriver (no seguro para producción)."""
    driver = webdriver.Firefox()
    driver.get(url)


if __name__ == '__main__':
    # Ejecución manual solo para desarrollo
    try:
        ingresar('https://linkedin.com')
    except Exception:
        pass
