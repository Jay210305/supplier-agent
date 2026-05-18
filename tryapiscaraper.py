import requests
from bs4 import BeautifulSoup

API_KEY = 'TU_API_KEY_AQUI'
TERMINO_BUSQUEDA = 'playstation+5'

# Vamos a iterar por las páginas del 1 al 3
for pagina in range(1, 4):
    print(f"\nObteniendo página {pagina}...")
    
    # 1. Construimos la URL de Amazon con el número de página
    amazon_url = f"https://www.amazon.com/s?k={TERMINO_BUSQUEDA}&page={pagina}"
    
    # 2. Preparamos los parámetros para ScraperAPI
    parametros = {
        'api_key': 'bdb1af0e2779e8b303a553d38fde3388',
        'url': amazon_url,
        'render': 'true',
        'country_code': 'us'
    }
    
    # 3. Hacemos la petición automática (esto reemplaza a tu comando curl)
    respuesta = requests.get('http://api.scraperapi.com', params=parametros)
    
    # Si la petición fue exitosa (Status 200)
    if respuesta.status_code == 200:
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        productos = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        print(f"--- Encontrados {len(productos)} productos en la página {pagina} ---")
        
        # 4. Extraemos como ya sabemos
        for producto in productos:
            titulo_elem = producto.find('span', class_='a-size-medium')
            titulo = titulo_elem.text.strip() if titulo_elem else "Sin título"
            
            precio_entero = producto.find('span', class_='a-price-whole')
            precio_decimal = producto.find('span', class_='a-price-fraction')
            
            if precio_entero and precio_decimal:
                precio_final = f"${precio_entero.text.strip()}{precio_decimal.text.strip()}"
                print(f"{titulo[:50]}... -> {precio_final}")
    else:
        print(f"Error al cargar la página {pagina}: Código {respuesta.status_code}")