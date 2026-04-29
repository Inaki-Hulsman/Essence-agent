from app.form.form_manager import FormManager


dic = {
  "produccion": {
    "meta": { "enabled": True },
    "perfil_responsable": [
      "Productor/a ejecutivo/a",
      "Productor/a creativo/a"
    ],
    "vision_estrategica": {
      "publico_objetivo": {
        "value": "",
        "status": "empty",
        "description": "Define el tipo de audiencia al que se dirige la película (edad, intereses, mercado)."
      },
      "posicionamiento": {
        "value": "",
        "status": "empty",
        "description": "Indica cómo se ubicará el proyecto en el mercado (comercial, autoral, festivales, plataformas)."
      },
      "escala_produccion": {
        "value": "",
        "status": "empty",
        "description": "Nivel de ambición y recursos de la producción (bajo, medio, alto presupuesto)."
      }
    },
    "identidad_del_proyecto": {
      "definicion_conceptual": {
        "value": "",
        "status": "empty",
        "description": "Resume el proyecto en una frase clara y concisa."
      },
      "propuesta_valor_diferencial": {
        "value": "",
        "status": "empty",
        "description": "Explica qué hace único al proyecto frente a otros similares."
      },
      "expectativa_mercado": {
        "value": "",
        "status": "empty",
        "description": "Describe el potencial comercial o de recepción del proyecto."
      }
    },
    "configuracion_del_equipo": {
      "perfil_director": {
        "value": "",
        "status": "empty",
        "description": "Define el tipo de director/a ideal para el proyecto."
      },
      "perfil_compositor": {
        "value": "",
        "status": "empty",
        "description": "Describe el perfil musical o estilo del compositor/a deseado."
      },
      "colaboradores_clave": {
        "value": "",
        "status": "empty",
        "description": "Lista de colaboradores estratégicos importantes para el proyecto."
      }
    }
  },
  "direccion": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Director/a"],
    "nota_de_direccion": {
      "vision_autoral": {
        "value": "",
        "status": "empty",
        "description": "Explica la mirada personal del director sobre la historia."
      },
      "referencias": {
        "value": "",
        "status": "empty",
        "description": "Incluye películas, obras o estilos que inspiran la dirección."
      },
      "tono_general": {
        "value": "",
        "status": "empty",
        "description": "Define el tono emocional y narrativo (dramático, ligero, oscuro, etc.)."
      }
    },
    "ritmo_y_narrativa": {
      "velocidad_narrativa": {
        "value": "",
        "status": "empty",
        "description": "Describe el ritmo general de la historia (lento, dinámico, variable)."
      },
      "uso_planos": {
        "value": "",
        "status": "empty",
        "description": "Define si predominan planos largos o montaje fragmentado."
      },
      "estructura": {
        "value": "",
        "status": "empty",
        "description": "Indica si la narrativa es clásica, lineal o experimental."
      }
    },
    "universo_visual": {
      "referencias_esteticas": {
        "value": "",
        "status": "empty",
        "description": "Referencias visuales que definen el estilo estético del proyecto."
      },
      "mood": {
        "value": "",
        "status": "empty",
        "description": "Describe la atmósfera emocional general de la película."
      },
      "color": {
        "value": "",
        "status": "empty",
        "description": "Define la aproximación al uso del color (paleta, contraste, simbolismo)."
      }
    }
  },
  "diseno_de_produccion": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Diseñador/a de Producción"],
    "estilo_global": {
      "sistema_formal": {
        "value": "",
        "status": "empty",
        "description": "Define las formas, texturas y coherencia visual del mundo."
      },
      "traduccion_vision_director": {
        "value": "",
        "status": "empty",
        "description": "Cómo se materializa la visión del director en lo visual."
      }
    },
    "reglas_del_universo": {
      "normas_visuales": {
        "value": "",
        "status": "empty",
        "description": "Reglas visuales que rigen el mundo narrativo."
      },
      "nivel_estilizacion": {
        "value": "",
        "status": "empty",
        "description": "Grado de realismo o estilización del entorno."
      }
    },
    "acting": {
      "tipo": {
        "value": "",
        "status": "empty",
        "description": "Define si la actuación es naturalista o estilizada."
      },
      "nivel_exageracion": {
        "value": "",
        "status": "empty",
        "description": "Nivel de exageración interpretativa, especialmente en animación."
      }
    }
  },
  "direccion_de_arte": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Director/a de Arte"],
    "escenarios": {
      "diseno_espacios": {
        "value": "",
        "status": "empty",
        "description": "Diseño visual de los espacios donde ocurre la acción."
      }
    },
    "objetos_y_atrezzo": {
      "elementos_identitarios": {
        "value": "",
        "status": "empty",
        "description": "Objetos clave que definen el mundo y los personajes."
      }
    },
    "vestuario": {
      "linea_estetica": {
        "value": "",
        "status": "empty",
        "description": "Estilo visual del vestuario y su coherencia con el universo."
      }
    }
  },
  "direccion_de_fotografia": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Director/a de Fotografía"],
    "camara_y_optica": {
      "lentes": {
        "value": "",
        "status": "empty",
        "description": "Tipo de lentes y su efecto visual en la imagen."
      },
      "movimiento_camara": {
        "value": "",
        "status": "empty",
        "description": "Uso del movimiento de cámara (estático, fluido, cámara en mano)."
      },
      "distorsiones_opticas": {
        "value": "",
        "status": "empty",
        "description": "Uso intencional de distorsiones o efectos ópticos."
      }
    },
    "encuadre_y_composicion": {
      "predominio_planos": {
        "value": "",
        "status": "empty",
        "description": "Tipos de plano más utilizados (primeros planos, generales, etc.)."
      },
      "geometria_visual": {
        "value": "",
        "status": "empty",
        "description": "Organización visual y composición dentro del encuadre."
      }
    },
    "luz_y_color": {
      "temperatura_color": {
        "value": "",
        "status": "empty",
        "description": "Sensación térmica del color (frío, cálido, neutro)."
      },
      "realismo_vs_estilizacion": {
        "value": "",
        "status": "empty",
        "description": "Equilibrio entre iluminación realista o estilizada."
      },
      "referencias_luminicas": {
        "value": "",
        "status": "empty",
        "description": "Referencias de iluminación (películas, estilos, artistas)."
      }
    },
    "textura_de_imagen": {
      "grano": {
        "value": "",
        "status": "empty",
        "description": "Nivel de grano o limpieza de la imagen."
      },
      "acabado": {
        "value": "",
        "status": "empty",
        "description": "Aspecto final (digital, orgánico, cinematográfico)."
      }
    }
  },
  "direccion_de_animacion": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Director/a de Animación"],
    "estilo_de_movimiento": {
      "tipo": {
        "value": "",
        "status": "empty",
        "description": "Tipo de movimiento (realista, cartoon, captura de movimiento)."
      },
      "referencias": {
        "value": "",
        "status": "empty",
        "description": "Referencias de estilo de animación."
      }
    },
    "fisica_y_elasticidad": {
      "leyes_fisicas": {
        "value": "",
        "status": "empty",
        "description": "Grado de respeto o ruptura de las leyes físicas."
      }
    },
    "acting_animado": {
      "expresividad": {
        "value": "",
        "status": "empty",
        "description": "Nivel de expresividad corporal y facial."
      }
    }
  },
  "direccion_de_iluminacion": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Lighting Director / Supervisor de Iluminación"],
    "diseno_luminico": {
      "tipo_luz": {
        "value": "",
        "status": "empty",
        "description": "Tipo de iluminación predominante."
      },
      "saturacion_contraste": {
        "value": "",
        "status": "empty",
        "description": "Nivel de saturación y contraste visual."
      }
    },
    "ambientacion": {
      "construccion_atmosferica": {
        "value": "",
        "status": "empty",
        "description": "Cómo la luz contribuye a la atmósfera."
      },
      "uso_sombras": {
        "value": "",
        "status": "empty",
        "description": "Uso dramático de las sombras."
      }
    }
  },
  "montaje": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Montador/a"],
    "ritmo": {
      "duracion_media_plano": {
        "value": "",
        "status": "empty",
        "description": "Duración promedio de los planos."
      },
      "intensidad_corte": {
        "value": "",
        "status": "empty",
        "description": "Frecuencia e intensidad de los cortes."
      }
    },
    "estilo_de_edicion": {
      "tipo": {
        "value": "",
        "status": "empty",
        "description": "Tipo de edición (clásica, experimental, videoclip)."
      },
      "relacion_redes": {
        "value": "",
        "status": "empty",
        "description": "Influencia de formatos de redes sociales o estética digital."
      }
    },
    "relectura_del_guion": {
      "grado_intervencion": {
        "value": "",
        "status": "empty",
        "description": "Nivel de cambios estructurales en montaje."
      }
    }
  },
  "musica_composicion": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Compositor/a"],
    "enfoque_musical": {
      "estilo": {
        "value": "",
        "status": "empty",
        "description": "Estilo musical predominante."
      },
      "instrumentacion": {
        "value": "",
        "status": "empty",
        "description": "Instrumentos principales utilizados."
      }
    },
    "funcion_dramatica": {
      "leitmotivs": {
        "value": "",
        "status": "empty",
        "description": "Uso de temas musicales asociados a personajes o ideas."
      },
      "rol_musica": {
        "value": "",
        "status": "empty",
        "description": "Rol de la música en la narrativa (protagonista o ambiental)."
      }
    }
  },
  "diseno_de_sonido": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Diseñador/a de Sonido"],
    "enfoque_sonoro": {
      "realismo_vs_estilizacion": {
        "value": "",
        "status": "empty",
        "description": "Nivel de realismo o estilización sonora."
      },
      "tipo_efectos": {
        "value": "",
        "status": "empty",
        "description": "Tipo de efectos (realistas, exagerados, cartoon)."
      }
    },
    "espacialidad": {
      "diseno_inmersivo": {
        "value": "",
        "status": "empty",
        "description": "Uso del sonido para generar inmersión."
      },
      "tratamiento_silencio": {
        "value": "",
        "status": "empty",
        "description": "Uso narrativo del silencio."
      }
    }
  },
  "casting_diseno_personajes": {
    "meta": { "enabled": True },
    "perfil_responsable": ["Director/a de Casting"],
    "enfoque_personajes": {
      "estilo": {
        "value": "",
        "status": "empty",
        "description": "Grado de naturalismo o estilización de los personajes."
      },
      "estetica": {
        "value": "",
        "status": "empty",
        "description": "Tipo de estética (normativa, estilizada, feísta, etc.)."
      }
    },
    "morfologia_animacion": {
      "proporciones": {
        "value": "",
        "status": "empty",
        "description": "Proporciones corporales de los personajes."
      },
      "nivel_caricaturizacion": {
        "value": "",
        "status": "empty",
        "description": "Nivel de exageración visual."
      }
    },
    "criterios_casting": {
      "tipo_actores": {
        "value": "",
        "status": "empty",
        "description": "Uso de actores profesionales o no profesionales."
      },
      "criterios_eleccion": {
        "value": "",
        "status": "empty",
        "description": "Criterios de selección (presencia, naturalidad, etc.)."
      }
    }
  },
  "coordinacion_general": {
    "meta": { "enabled": True },
    "perfil_responsable": [
      "Dirección",
      "Producción"
    ],
    "coherencia_global": {
      "elementos_transversales": {
        "value": "",
        "status": "empty",
        "description": "Elementos que deben mantenerse coherentes en todo el proyecto."
      },
      "lineas_rojas": {
        "value": "",
        "status": "empty",
        "description": "Decisiones creativas que no deben modificarse."
      }
    },
    "riesgos_asumidos": {
      "decisiones_no_convencionales": {
        "value": "",
        "status": "empty",
        "description": "Decisiones creativas arriesgadas o poco convencionales."
      },
      "apuesta_diferencial": {
        "value": "",
        "status": "empty",
        "description": "Elemento diferencial clave del proyecto."
      }
    }
  }
}




# Diccionario de ejemplo
data = {
    "produccion": {
        "meta": {"enabled": True},
        "perfil_responsable": [
            "Productor/a ejecutivo/a",
            "Productor/a creativo/a"
        ],
        "vision_estrategica": {
            "publico_objetivo": {
                "value": "",
                "status": "empty",
                "description": "Define el tipo de audiencia al que se dirige la película (edad, intereses, mercado)."
            },
            "posicionamiento": {
                "value": "",
                "status": "empty",
                "description": "Indica cómo se ubicará el proyecto en el mercado (comercial, autoral, festivales, plataformas)."
            },
            "escala_produccion": {
                "value": "",
                "status": "empty",
                "description": "Nivel de ambición y recursos de la producción (bajo, medio, alto presupuesto)."
            }
        }
    }
}

# # Crear modelo dinámico Produccion
form_manager = FormManager()

print(form_manager.get_fields_path(dic))
