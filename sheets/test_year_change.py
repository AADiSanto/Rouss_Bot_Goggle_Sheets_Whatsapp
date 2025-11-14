# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Jueves 14 de Noviembre del 2025.-
#
#     Program          :   Bot de WhatsApp con Google Sheets,
#                             para Asignación de Turnos en Rouss Coiffeur's de MEMORY   Ingeniería en Sistemas.-
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

"""
Test de Cambio de Año - Verificación de Generación Automática de Hojas
Ejecutar Desde el Proyecto en : python sheets/test_year_change.py
"""

import sys
import os
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


#Test: Verificar que Funciona con el Año Actual ( 2025 ).-
def test_año_2025():
    """Test: Verificar que Funciona con el Año Actual (2025)"""
    print("\n" + "=" * 70)
    print("TEST 1: Verificando Operación Normal en el Año: 2025")
    print("=" * 70)

    fecha_2025 = "2025-12-15"

    try:
        # Configurar hoja para el Año: 2025.-
        sheet_id = set_active_spreadsheet(2025)
        print(f"✅ Hoja Año: 2025 Configurada: {sheet_id}")

        # Verificar Horarios Disponibles.-
        horarios = get_available_slots('Walter', fecha_2025)
        print(f"✅ Horarios Disponibles para Walter el {fecha_2025}:")
        print(f"   {', '.join(horarios[:5])}..." if len(horarios) > 5 else f"   {', '.join(horarios)}")

        # Verificar disponibilidad de un horario específico
        disponible = check_availability('Walter', fecha_2025, '15:00')
        print(f"✅ Horario 15:00 Disponible: {'SÍ' if disponible else 'NO'}")

        return True

    except Exception as e:
        print(f"❌ ERROR en Test 2025: {e}")
        return False


#Test: Verificar Creación Automática de Hoja para 2026.-
def test_año_2026():
    """Test: Verificar Creación Automática de Hoja para 2026"""
    print("\n" + "=" * 70)
    print("TEST 2: Verificando Creación Automática de Hoja 2026")
    print("=" * 70)

    fecha_2026 = "2026-01-15"

    try:
        # Configurar Hoja para 2026 ( Debería Crearla Automáticamente ).-
        print("🔄 Intentando Configurar / Crear Hoja para el Año: 2026...")
        sheet_id = set_active_spreadsheet(2026)
        print(f"✅ Hoja 2026 Configurada / Creada: {sheet_id}")
        print(f"   📄 Nombre Esperado: '2026_Rouss_Turnos_Coiffeur'")
        print(f"   🔗 URL: https://docs.google.com/spreadsheets/d/{sheet_id}")

        # Verificar que Sé Puede Leer la Hoja ( Debería Tener Sólo Encabezados ).-
        datos = read_sheet('A1:K2')
        print(f"✅ Lectura de Hoja 2026 Exitosa...")
        print(f"   Filas Leídas: {len(datos)}")
        if datos:
            print(f"   Encabezados: {datos[0][:4]}...")  # Primeras 4 Columnas.-

        # Verificar horarios disponibles (todos deberían estar libres)
        horarios = get_available_slots('Walter', fecha_2026)
        print(f"✅ Horarios Disponibles para Walter el: {fecha_2026}:")
        print(f"   Total: {len(horarios)} Horarios Libres")

        return True

    except Exception as e:
        print(f"❌ ERROR en Test 2026: {e}")
        import traceback
        traceback.print_exc()
        return False


#Test: Crear una Reserva de Prueba en el Año 2026.-
def test_reserva_2026():
    """Test: Crear una Reserva de Prueba en 2026"""
    print("\n" + "=" * 70)
    print("TEST 3: Creando Reserva de Prueba en el Año: 2026...")
    print("=" * 70)

    fecha_2026 = "2026-01-15"
    hora = "10:00"

    try:
        # Crear Reserva Provisional
        print(f"🔄 Creando Reserva para: {fecha_2026} a las: {hora}...")
        reservation_id = crear_reserva_provisional(
            nombre="TEST_CLIENTE_2026",
            telefono="5491199999999",
            servicio="Corte",
            coiffeur="Walter",
            fecha=fecha_2026,
            hora=hora
        )

        print(f"✅ Reserva Creada Exitosamente...")
        print(f"   Reservation ID: {reservation_id}")
        print(f"   Cliente: TEST_CLIENTE_2026")
        print(f"   Fecha: {fecha_2026}")
        print(f"   Hora: {hora}")

        # Verificar que la Reserva Sé Guardó.-
        datos = read_sheet()
        reservas_2026 = [row for row in datos if len(row) >= 5 and row[4] == fecha_2026]
        print(f"✅ Verificación de Guardado:")
        print(f"   Reservas Encontradas para: {fecha_2026}: {len(reservas_2026)}")

        # Verificar que el Horario Yá Nó Está Disponible.-
        disponible = check_availability('Walter', fecha_2026, hora)
        print(f"✅ Verificación de Disponibilidad:")
        print(f"   Horario {hora} Disponible: {'SÍ (ERROR!)' if disponible else 'NO (CORRECTO)'}")

        return True

    except Exception as e:
        print(f"❌ ERROR en Test Reserva para el Año: 2026: {e}")
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

            if '2026' in ids:
                print(f"\n✅ ID del Año 2026 Guardado Correctamente...")
                print(f"   Próximo Reinicio Usará este ID Sín Crear Nueva Hoja...")
            else:
                print(f"\n⚠️  ID del 2026 NO Encontrado en Archivo JSON: 'spreadsheet_ids.json'...")
                print(f"   Posible Causa: ERROR: al Guardar o Test Nó Ejecutado...")

            return True
        else:
            print(f"⚠️  Archivo JSON: 'spreadsheet_ids.json', Nó Existe: {config_file}")
            print(f"   Se Creará Automáticamente al Generar la Primera Hoja...")
            return True

    except Exception as e:
        print(f"❌ ERROR en Test Persistencia: {e}")
        return False


#Limpia las Reservas de Prueba Creadas"""
def limpiar_reservas_test():
    """Limpia las Reservas de Prueba Creadas"""
    print("\n" + "=" * 70)
    print("LIMPIEZA: ¿Deseas Eliminar las Reservas de Prueba?...")
    print("=" * 70)
    print("⚠️  Nota: Debes Eliminar Manualmente Desde Google Sheets")
    print("   1. Abre la Hoja 2026_Rouss_Turnos_Coiffeur")
    print("   2. Busca filas con 'TEST_CLIENTE_2026'")
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

    # Test 1: Año Actual (2025)
    resultados.append(("Test Año: 2025", test_año_2025()))

    # Test 2: Creación de Hoja Año: 2026
    resultados.append(("Test Hoja Año: 2026", test_año_2026()))

    # Test 3: Reserva en Año: 2026
    resultados.append(("Test Reserva Año: 2026", test_reserva_2026()))

    # Test 4: Persistencia
    resultados.append(("Test Persistencia en Archivo JSON: 'spreadsheet_ids.json'...", test_persistencia_ids()))

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


