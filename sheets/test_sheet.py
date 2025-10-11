# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program: Bot de WhatsApp con Google Sheets,
#                 para Asignación de Turnos en Rouss Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
# *********************************************************************************************************************
#
#  *** Python v3.13.6
#
#  *** Compilar en el Directorio del Programa desde PowerShell como Administrador ( Nó es Necesario ).-
#
#  ***     pyinstaller --onefile --noconsole Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#          Para Incluír un ícono en el .exe:
#
#          Buscar el Icono en: https://www.svgrepo.com/
#
#             Guardarlo como .svg
#
#          Luego Converirlo de .svg a .ico en: https://convertico.com/es/svg-a-ico/
#
#  ***     pyinstaller --onefile --icon=MosFET.ico Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#  ***        El .exe Compilado Estará Dentro de la Carpeta "dist".-
#
# *********************************************************************************************************************

"""
test_sheet.py
Testear Lectura de la Planilla de Excel.-
"""

from sheet_service import read_sheet
data = read_sheet()  # La Función sé Ejecuta Aquí.-
print(data)          # El Resultado De ésta Función Sé Imprime Aquí.-


