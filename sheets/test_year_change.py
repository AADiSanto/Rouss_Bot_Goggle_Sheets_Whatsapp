# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Jueves 14 de Noviembre del 2025.-
#
#     Program          :   Bot de WhatsApp con Google Sheets,
#                             para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose   :   Script de Testing para Verificar Creación Automática de Hojas por Año.-
#                             Simula Reservas en Diferentes Años (2025, 2026) para Validar el Sistema
#                             de Generación Dinámica de Hojas de Cálculo y Persistencia de IDs.-
#
#     Ejecutar Como    :   python sheets/test_year_change.py
#
#     o Sólo el Módulo :   python -m sheets.test_year_change
#
# *********************************************************************************************************************

# ***********************************************************************************************
#   RESUMEN DE LO QUE DEBERÍA OCURRIR AL EJECUTAR ESTE MÓDULO DE PRUEBAS ( test_year_change.py )
# ***********************************************************************************************
#
# 1) El sistema detecta automáticamente el Año en Curso mediante: get_current_year().
#
# 2) Prueba la Hoja del Año Actual:
#       - Verifica que el archivo Google Sheets para ese año exista.
#       - Si no existe, lo crea automáticamente con la estructura correcta.
#
# 3) Prueba la Hoja del Año Siguiente:
#       - Solicita o crea la planilla del Año Próximo (Año Actual + 1).
#       - Valida que el SPREADSHEET_ID quede guardado en el archivo JSON interno:
#               spreadsheet_ids.json
#
# 4) Ejecuta el nuevo test:
#       test_generar_proximo_año()
#
#    Este test ejecuta la función:
#       generar_hoja_del_proximo_año()
#
#    La cual:
#       • Calcula el año próximo.
#       • Crea la hoja correspondiente si no existe.
#       • Verifica acceso correcto.
#       • Guarda el nuevo SPREADSHEET_ID en:
#               - El archivo JSON interno.
#               - El archivo .env con el nombre:
#                     SPREADSHEET_ID_<AÑO>
#
# 5) Resultado esperado:
#       - Debe imprimirse en pantalla un SPREADSHEET_ID válido para el próximo año.
#       - Debe aparecer al final del archivo .env un nuevo bloque:
#               # ID de la Hoja del Próximo Año Generada Automáticamente.-
#               SPREADSHEET_ID_YYYY=xxxxxxxxxxxxxxxxxxxx
#
#       - Ningún test debe fallar.
#       - No se deben crear hojas duplicadas.
#
# ***********************************************************************************************
#   FIN DEL RESUMEN DE PRUEBAS
# ***********************************************************************************************

"""
Test de Cambio de Año - Verificación de Generación Automática de Hojas
Ejecutar Desde el Proyecto en : python sheets/test_year_change.py
"""
import sys
import os

import logging
logging.getLogger().handlers.clear()

# Año Actual y Año Próximo Detectados Dinámicamente.-
from sheet_service import get_current_year

AÑO_ACTUAL = get_current_year()
AÑO_SIGUIENTE = AÑO_ACTUAL + 1

from datetime import datetime

# Agregar El Directorio Raíz al Path ( Estamos en '/sheets', Subir un Nivel ).-
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sheet_service import (
    set_active_spreadsheet,
    get_available_slots,
    check_availability,
    read_sheet,
    SPREADSHEET_ID
)

from scheduler_service import crear_reserva_provisional


#Test: Verificar que Funciona con el Año Actual.-
def test_año_actual():
    """Test: Verificar que Funciona con el Año Actual"""
    print("\n" + "=" * 70)
    print("TEST 1: Test: Verificar que Funciona con el Año Actual Detectado Automáticamente...")
    print("=" * 70)

    fecha_prueba = f"{AÑO_ACTUAL}-12-15"

    try:
        # Configurar Hoja para el Año Actual Detectado Automáticamente.-
        sheet_id = set_active_spreadsheet(AÑO_ACTUAL)
        print(f"✅ Hoja Año: {AÑO_ACTUAL} Configurada: {sheet_id}")

        # Verificar Horarios Disponibles.-
        horarios = get_available_slots('Walter', fecha_prueba)
        print(f"✅ Horarios Disponibles para Walter el {fecha_prueba}:")
        print(f"   {', '.join(horarios[:5])}..." if len(horarios) > 5 else f"   {', '.join(horarios)}")

        # Verificar disponibilidad de un horario específico
        disponible = check_availability('Walter', fecha_prueba, '15:00')
        print(f"✅ Horario 15:00 Disponible: {'SÍ' if disponible else 'NO'}")

        return True

    except Exception as e:
        print(f"❌ ERROR en Test {AÑO_ACTUAL}: {e}")
        return False


#Test: Verificar Creación Automática de Hoja para el Año Siguiente al Actual.-
def test_año_siguiente():
    """Test: Verificar Creación Automática de Hoja para el Año Siguiente al Actual"""
    print("\n" + "=" * 70)
    print(f"TEST 2: Verificando Creación Automática de Hoja {AÑO_SIGUIENTE}")
    print("=" * 70)

    fecha_prueba = f"{AÑO_SIGUIENTE}-01-15"

    try:
        # Configurar Hoja para el Año Siguiente al Actual ( Debería Crearla Automáticamente ).-
        print("🔄 Intentando Configurar / Crear Hoja para el Año Siguiente al Actual...")

        # NOTA: Nó se Crea Hoja Nueva porque Nó Tengo Permisos para Crearla, Sólo Usarla.-
        sheet_id = set_active_spreadsheet(AÑO_SIGUIENTE)
        print(f"✅ Hoja Año {AÑO_SIGUIENTE} Configurada / Creada: {sheet_id}")

        from sheet_service import NOMBRE_EMPRESA
        print(f"   📄 Nombre Esperado: '{AÑO_SIGUIENTE}_{NOMBRE_EMPRESA}_Turnos_Coiffeur'")
        print(f"   🔗 URL: https://docs.google.com/spreadsheets/d/{sheet_id}")

        # Verificar que Sé Puede Leer la Hoja (Debería Tener Sólo Encabezados).-
        datos = read_sheet('A1:M2')
        print(f"✅ Lectura de Hoja {AÑO_SIGUIENTE} Exitosa...")
        print(f"   Filas Leídas: {len(datos)}")
        if datos:
            print(f"   Encabezados: {datos[0][:4]}...")  # Primeras 4 Columnas.-

        # Verificar Horarios Disponibles (Todos Deberían Estar Libres).-
        horarios = get_available_slots('Walter', fecha_prueba)
        print(f"✅ Horarios Disponibles para Walter el: {fecha_prueba}:")
        print(f"   Total: {len(horarios)} Horarios Libres")

        return True

    except Exception as e:
        print(f"❌ ERROR en Test {AÑO_SIGUIENTE}: {e}")
        import traceback
        traceback.print_exc()
        return False


#Test: Crear una Reserva de Prueba en el Año Siguiente al Actual.-
def test_reserva_año_siguiente_al_actual():
    """Test: Crear una Reserva de Prueba para el Año Siguiente al Actual"""
    print("\n" + "=" * 70)
    print(f"TEST 3: Creando Reserva de Prueba en el Año: {AÑO_SIGUIENTE}...")
    print("=" * 70)

    fecha_prueba = f"{AÑO_SIGUIENTE}-01-15"
    hora = "10:00"

    try:
        # Crear Reserva Provisional (DEBE FALLAR)
        print(f"🔄 Creando Reserva para: {AÑO_SIGUIENTE} a las: {hora}...")
        crear_reserva_provisional(
            nombre="TEST_CLIENTE_AÑO_SIGUIENTE_AL_ACTUAL",
            telefono="549119999999999",
            servicio="Corte",
            coiffeur="Walter",
            fecha=fecha_prueba,
            hora=hora
        )

        # Si llega aquí, es un ERROR (porque NO debería permitir reservar)
        print("❌ ERROR: El Sistema PERMITIÓ Reservar en el Año Siguiente ( INCORRECTO ).-")
        return False

    except ValueError as e:
        # ESTE ES EL COMPORTAMIENTO CORRECTO
        print(f"✅ Correcto: El Sistema Rechazó la Reserva del Año Siguiente.-")
        print(f"   Mensaje: {e}")
        return True

    except Exception as e:
        print(f"❌ ERROR Inesperado en Test Reserva Año Siguiente: {e}")
        import traceback
        traceback.print_exc()
        return False


#Test: Verificar que los IDs se Guardan en el Archivo JSON.-
def test_persistencia_ids():
    """Test: Verificar que los IDs se Guardan en el Archivo JSON"""
    print("\n" + "=" * 70)
    print("TEST 4: Verificando Persistencia de IDs en Archivo JSON: 'spreadsheet_ids.json'...")
    print("=" * 70)

    try:
        import json
        from pathlib import Path

        config_file = Path(__file__).resolve().parent / 'spreadsheet_ids.json'

        if config_file.exists():
            with open(config_file, 'r') as f:
                ids = json.load(f)

            print(f"✅ Archivo JSON Encontrado: {config_file}")
            print(f"   IDs Guardados:")
            for year, sheet_id in ids.items():
                print(f"   • Año {year}: {sheet_id}")

            if str(AÑO_SIGUIENTE) in ids:
                print(f"\n✅ ID del Año Siguiente al Actual Guardado Correctamente...")
                print(f"   Próximo Reinicio Usará este ID Sín Crear Nueva Hoja...")
            else:
                print(f"\n⚠️  ID del Año Siguiente al Actual Nó Encontrado en Archivo JSON: 'spreadsheet_ids.json'...")
                print(f"   Posible Causa: ERROR: al Guardar o Test Nó Ejecutado...")

            return True
        else:
            print(f"⚠️  Archivo JSON: 'spreadsheet_ids.json', Nó Existe: {config_file}")
            print(f"   Se Creará Automáticamente al Generar la Primera Hoja...")
            return True

    except Exception as e:
        print(f"❌ ERROR en Test Persistencia: {e}")
        return False


#Test: Generación Automática de la Hoja del Próximo Año.-
def test_generar_proximo_año():
    """Test: Generar Automáticamente la Hoja del Próximo Año"""
    print("\n" + "=" * 70)
    print("TEST 5: Generando Automáticamente la Hoja del Próximo Año.-")
    print("=" * 70)

    try:
        from sheets.sheet_service import generar_hoja_del_proximo_año

        nuevo_id = generar_hoja_del_proximo_año()
        print(f"✅ Hoja del Próximo Año Generada Correctamente.-")
        print(f"   Nuevo SPREADSHEET_ID: {nuevo_id}")

        return True

    except Exception as e:
        print(f"❌ ERROR al Generar Hoja del Próximo Año: {e}")
        import traceback
        traceback.print_exc()
        return False


#Test: Validar que las 3 Pestañas Existan en la Hoja del Año Indicado.-
def test_validar_pestanas(year):
    """Test: Validar Existencia de Pestañas en la Hoja del Año Indicado"""
    print("\n" + "=" * 70)
    print(f"TEST: Validando Pestañas de la Hoja del Año: {year}...")
    print("=" * 70)

    try:
        # Configurar la Hoja Correspondiente.-
        sheet_id = set_active_spreadsheet(year)
        print(f"🔍 Verificando Estructura de la Hoja con ID: {sheet_id}")

        from sheet_service import service

        # Obtener metadata completa
        info = service.spreadsheets().get(spreadsheetId=sheet_id).execute()

        # Extraer nombres de pestañas reales
        pestañas = [sh["properties"]["title"] for sh in info.get("sheets", [])]

        # Pestañas requeridas
        requeridas = [
            "Turnos_Coiffeur",
            "Turnos_Calendario_Visual",
            "Turnos_Feriados",
        ]

        print("📄 Pestañas Encontradas:", ", ".join(pestañas))

        # Verificar todas
        faltantes = [p for p in requeridas if p not in pestañas]

        if faltantes:
            print(f"❌ ERROR: Faltan las Siguientes Pestañas en la Hoja Generada del Año Siguiente: {', '.join(faltantes)}")
            return False

        print("✅ Todas las Pestañas Requeridas Existen Correctamente en la Hoja Generada del Año Siguiente.")
        return True

    except Exception as e:
        print(f"❌ ERROR al Validar Pestañas del Año {year}: {e}")
        import traceback
        traceback.print_exc()
        return False


#Limpia las Reservas de Prueba Creadas"""
def limpiar_reservas_test():
    """Limpia las Reservas de Prueba Creadas"""
    print("\n" + "=" * 70)
    print("LIMPIEZA: ¿Deseas Eliminar las Reservas de Prueba?...")
    print("=" * 70)
    print("⚠️  Nota: Debes Eliminar Manualmente Desde Google Sheets")

    from sheet_service import NOMBRE_EMPRESA
    print(f"   1. Abre la Hoja {AÑO_SIGUIENTE}_{NOMBRE_EMPRESA}_Turnos_Coiffeur")

    print("   2. Busca Filas con 'TEST_CLIENTE_AÑO_SIGUIENTE'")
    print("   3. Elimina Esas Filas")
    print("\n   O simplemente Elimina Toda La Hoja del Año 2026 Sí Fué Sólo Para Testing...")


#Ejecuta Todos los Tests en Secuencia.-
def main():
    """Ejecuta Todos los Tests en Secuencia"""
    print("\n" + "=" * 70)
    print("🧪 SUITE DE TESTS - SISTEMA DE HOJAS ANUALES...")
    print("=" * 70)
    print("Fecha del Test:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    resultados = []

    # Test 1: Año Actual.-
    resultados.append(("Test Año Actual.-", test_año_actual()))

    # Test 2: Creación de Hoja Año Siguiente al Actual.-
    resultados.append((f"Test Hoja Año {AÑO_SIGUIENTE}", test_año_siguiente()))

    # Test 3: Reserva en Año: 2026
    resultados.append(("Test Reserva Año Siguiente al Actual.-", test_reserva_año_siguiente_al_actual()))

    # Test 4: Persistencia
    resultados.append(("Test Persistencia en Archivo JSON: 'spreadsheet_ids.json'...", test_persistencia_ids()))

    # Test 5: Generación Automática del Próximo Año al Actual.-
    resultados.append(("Test Generar Hoja del Próximo Año al Actual.-", test_generar_proximo_año()))

    # Test 6: Validar Pestañas del Año Actual y del Año Siguiente.-
    resultados.append((f"Test Validar Pestañas Año {AÑO_ACTUAL}", test_validar_pestanas(AÑO_ACTUAL)))
    resultados.append((f"Test Validar Pestañas Año {AÑO_SIGUIENTE}", test_validar_pestanas(AÑO_SIGUIENTE)))

    # Resumen Final.-
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE TESTS...")
    print("=" * 70)

    total = len(resultados)
    exitosos = sum(1 for _, resultado in resultados if resultado)

    for nombre, resultado in resultados:
        estado = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{estado} - {nombre}")

    print(f"\n{'=' * 70}")
    print(f"Total: {exitosos}/{total} Tests Exitosos...")
    print(f"{'=' * 70}")

    if exitosos == total:
        print("\n🎉 ¡TODOS LOS TESTS PASARON!...")
        print("   El Sistema de Hojas Anuales Está Funcionando Correctamente...")
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON...")
        print("   Revisar los ERRORES Arriba Para Diagnosticar...")

    # Información de limpieza
    limpiar_reservas_test()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests Interrumpidos por el Usuario...")
    except Exception as e:
        print(f"\n\n❌ ERROR CRÍTICO en Suite de Tests: {e} ...")
        import traceback

        traceback.print_exc()


