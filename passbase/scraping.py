from selenium import webdriver


def ingresar(url): ## ver esto
        
    driver = webdriver.Firefox()
    driver.get(url)

resultado = ingresar('https://linkedin.com')
