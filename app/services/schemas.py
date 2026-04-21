# app/schemas.py
from pydantic import BaseModel, create_model
from typing import Literal, Optional, List, Dict, Any, ClassVar, Type



class LLMResponse(BaseModel):
    reply: str
    extracted_fields: Dict[str, Any]

    def to_dict(self):
        return {
            "reply": self.reply,
            "extracted_fields": self.extracted_fields
        }

class Field_Text(BaseModel):
    value: str = ""
    status: Literal["empty", "agent", "user", "default", "image_ref"] = "empty"
    description: Optional[str] = None

DESCRIPCIONES = {
    # PRODUCCION
    "produccion.vision_estrategica.publico_objetivo": "Define el tipo de audiencia al que se dirige la película (edad, intereses, mercado).",
    "produccion.vision_estrategica.posicionamiento": "Indica cómo se ubicará el proyecto en el mercado (comercial, autoral, festivales, plataformas).",
    "produccion.vision_estrategica.escala_produccion": "Nivel de ambición y recursos de la producción (bajo, medio, alto presupuesto).",
    "produccion.identidad_del_proyecto.definicion_conceptual": "Resume el proyecto en una frase clara y concisa.",
    "produccion.identidad_del_proyecto.propuesta_valor_diferencial": "Explica qué hace único al proyecto frente a otros similares.",
    "produccion.identidad_del_proyecto.expectativa_mercado": "Describe el potencial comercial o de recepción del proyecto.",
    "produccion.configuracion_del_equipo.perfil_director": "Define el tipo de director/a ideal para el proyecto.",
    "produccion.configuracion_del_equipo.perfil_compositor": "Describe el perfil musical o estilo del compositor/a deseado.",
    "produccion.configuracion_del_equipo.colaboradores_clave": "Lista de colaboradores estratégicos importantes para el proyecto.",

    # DIRECCION
    "direccion.nota_de_direccion.vision_autoral": "Explica la mirada personal del director sobre la historia.",
    "direccion.nota_de_direccion.referencias": "Incluye películas, obras o estilos que inspiran la dirección.",
    "direccion.nota_de_direccion.tono_general": "Define el tono emocional y narrativo (dramático, ligero, oscuro, etc.).",
    "direccion.ritmo_y_narrativa.velocidad_narrativa": "Describe el ritmo general de la historia (lento, dinámico, variable).",
    "direccion.ritmo_y_narrativa.uso_planos": "Define si predominan planos largos o montaje fragmentado.",
    "direccion.ritmo_y_narrativa.estructura": "Indica si la narrativa es clásica, lineal o experimental.",
    "direccion.universo_visual.referencias_esteticas": "Referencias visuales que definen el estilo estético del proyecto.",
    "direccion.universo_visual.mood": "Describe la atmósfera emocional general de la película.",
    "direccion.universo_visual.color": "Define la aproximación al uso del color (paleta, contraste, simbolismo).",

    # DISEÑO DE PRODUCCION
    "diseno_de_produccion.estilo_global.sistema_formal": "Define las formas, texturas y coherencia visual del mundo.",
    "diseno_de_produccion.estilo_global.traduccion_vision_director": "Cómo se materializa la visión del director en lo visual.",
    "diseno_de_produccion.reglas_del_universo.normas_visuales": "Reglas visuales que rigen el mundo narrativo.",
    "diseno_de_produccion.reglas_del_universo.nivel_estilizacion": "Grado de realismo o estilización del entorno.",
    "diseno_de_produccion.acting.tipo": "Define si la actuación es naturalista o estilizada.",
    "diseno_de_produccion.acting.nivel_exageracion": "Nivel de exageración interpretativa, especialmente en animación.",

    # DIRECCION DE ARTE
    "direccion_de_arte.escenarios.diseno_espacios": "Diseño visual de los espacios donde ocurre la acción.",
    "direccion_de_arte.objetos_y_atrezzo.elementos_identitarios": "Objetos clave que definen el mundo y los personajes.",
    "direccion_de_arte.vestuario.linea_estetica": "Estilo visual del vestuario y su coherencia con el universo.",

    # DIRECCION DE FOTOGRAFIA
    "direccion_de_fotografia.camara_y_optica.lentes": "Tipo de lentes y su efecto visual en la imagen.",
    "direccion_de_fotografia.camara_y_optica.movimiento_camara": "Uso del movimiento de cámara (estático, fluido, cámara en mano).",
    "direccion_de_fotografia.camara_y_optica.distorsiones_opticas": "Uso intencional de distorsiones o efectos ópticos.",
    "direccion_de_fotografia.encuadre_y_composicion.predominio_planos": "Tipos de plano más utilizados (primeros planos, generales, etc.).",
    "direccion_de_fotografia.encuadre_y_composicion.geometria_visual": "Organización visual y composición dentro del encuadre.",
    "direccion_de_fotografia.luz_y_color.temperatura_color": "Sensación térmica del color (frío, cálido, neutro).",
    "direccion_de_fotografia.luz_y_color.realismo_vs_estilizacion": "Equilibrio entre iluminación realista o estilizada.",
    "direccion_de_fotografia.luz_y_color.referencias_luminicas": "Referencias de iluminación (películas, estilos, artistas).",
    "direccion_de_fotografia.textura_de_imagen.grano": "Nivel de grano o limpieza de la imagen.",
    "direccion_de_fotografia.textura_de_imagen.acabado": "Aspecto final (digital, orgánico, cinematográfico).",

    # DIRECCION DE ANIMACION
    "direccion_de_animacion.aplica": "Indica si el proyecto incluye animación.",
    "direccion_de_animacion.estilo_de_movimiento.tipo": "Tipo de movimiento (realista, cartoon, captura de movimiento).",
    "direccion_de_animacion.estilo_de_movimiento.referencias": "Referencias de estilo de animación.",
    "direccion_de_animacion.fisica_y_elasticidad.leyes_fisicas": "Grado de respeto o ruptura de las leyes físicas.",
    "direccion_de_animacion.acting_animado.expresividad": "Nivel de expresividad corporal y facial.",

    # DIRECCION DE ILUMINACION
    "direccion_de_iluminacion.diseno_luminico.tipo_luz": "Tipo de iluminación predominante.",
    "direccion_de_iluminacion.diseno_luminico.saturacion_contraste": "Nivel de saturación y contraste visual.",
    "direccion_de_iluminacion.ambientacion.construccion_atmosferica": "Cómo la luz contribuye a la atmósfera.",
    "direccion_de_iluminacion.ambientacion.uso_sombras": "Uso dramático de las sombras.",

    # MONTAJE
    "montaje.ritmo.duracion_media_plano": "Duración promedio de los planos.",
    "montaje.ritmo.intensidad_corte": "Frecuencia e intensidad de los cortes.",
    "montaje.estilo_de_edicion.tipo": "Tipo de edición (clásica, experimental, videoclip).",
    "montaje.estilo_de_edicion.relacion_redes": "Influencia de formatos de redes sociales o estética digital.",
    "montaje.relectura_del_guion.grado_intervencion": "Nivel de cambios estructurales en montaje.",

    # MUSICA Y COMPOSICION
    "musica_composicion.enfoque_musical.estilo": "Estilo musical predominante.",
    "musica_composicion.enfoque_musical.instrumentacion": "Instrumentos principales utilizados.",
    "musica_composicion.funcion_dramatica.leitmotivs": "Uso de temas musicales asociados a personajes o ideas.",
    "musica_composicion.funcion_dramatica.rol_musica": "Rol de la música en la narrativa (protagonista o ambiental).",

    # DISEÑO DE SONIDO
    "diseno_de_sonido.enfoque_sonoro.realismo_vs_estilizacion": "Nivel de realismo o estilización sonora.",
    "diseno_de_sonido.enfoque_sonoro.tipo_efectos": "Tipo de efectos (realistas, exagerados, cartoon).",
    "diseno_de_sonido.espacialidad.diseno_inmersivo": "Uso del sonido para generar inmersión.",
    "diseno_de_sonido.espacialidad.tratamiento_silencio": "Uso narrativo del silencio.",

    # CASTING Y PERSONAJES
    "casting_diseno_personajes.enfoque_personajes.estilo": "Grado de naturalismo o estilización de los personajes.",
    "casting_diseno_personajes.enfoque_personajes.estetica": "Tipo de estética (normativa, estilizada, feísta, etc.).",
    "casting_diseno_personajes.morfologia_animacion.proporciones": "Proporciones corporales de los personajes.",
    "casting_diseno_personajes.morfologia_animacion.nivel_caricaturizacion": "Nivel de exageración visual.",
    "casting_diseno_personajes.criterios_casting.tipo_actores": "Uso de actores profesionales o no profesionales.",
    "casting_diseno_personajes.criterios_casting.criterios_eleccion": "Criterios de selección (presencia, naturalidad, etc.).",

    # COORDINACION GENERAL
    "coordinacion_general.coherencia_global.elementos_transversales": "Elementos que deben mantenerse coherentes en todo el proyecto.",
    "coordinacion_general.coherencia_global.lineas_rojas": "Decisiones creativas que no deben modificarse.",
    "coordinacion_general.riesgos_asumidos.decisiones_no_convencionales": "Decisiones creativas arriesgadas o poco convencionales.",
    "coordinacion_general.riesgos_asumidos.apuesta_diferencial": "Elemento diferencial clave del proyecto."
}


def dict_to_custom_class(name: str, d: Dict[str, Any]) -> BaseModel:
    """
    Convierte un diccionario en un modelo Pydantic dinámico.
    """
    fields = {}
    for k, v in d.items():
        if isinstance(v, dict):
            # Si parece un Field
            if set(v.keys()) >= Field_Text.model_fields.keys():
                fields[k] = (Field_Text, Field_Text(**v))
            else:
                # Crear modelo anidado recursivamente
                nested_model = dict_to_custom_class(k.capitalize(), v)
                fields[k] = (nested_model, nested_model(**v)) # type: ignore
        elif isinstance(v, list):
            # Convertir listas a esquemas tipados, especialmente list[str]
            if len(v) > 0:
                item_type = type(v[0])
                fields[k] = (List[item_type], v)
            else:
                fields[k] = (List[str], v)
        else:
            # Para valores simples
            fields[k] = (type(v), v)
    
    # Crear modelo dinámico
    model = create_model(name, **fields)
    return model # type: ignore

