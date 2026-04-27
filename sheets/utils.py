# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   utils.py | Funciones Helper's.-
#
# *********************************************************************************************************************


# ------------------------------------------------
# HELPERS / NORMALIZACIÓN
# ------------------------------------------------

def normalizar_hora(hora_str):
    try:
        h, m = hora_str.strip().split(':')
        return f"{int(h):02d}:{m}"
    except:
        return hora_str.strip()


def hora_a_time(hora_str):
    from datetime import datetime
    try:
        h, m = hora_str.strip().split(':')
        return datetime.strptime(f"{int(h):02d}:{m}", "%H:%M").time()
    except:
        return None



