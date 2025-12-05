import logging
import sys
import os
from datetime import datetime

_loggers = {}  # Diccionario para manejar múltiples archivos sin duplicar handlers


def log_custom(section=None, message=None, level="INFO", file=None):
    """
    Registra eventos personalizados en consola y archivo.

    Args:
        section (str): Nombre de la sección.
        message (str): Mensaje a registrar.
        level (str): Nivel del log ('INFO', 'WARNING', 'ERROR').
        file (str, optional): Ruta del archivo log.
    """

    # Formato simple para consola
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Construir mensaje de consola
    if section and message:
        console_msg = f"[{level}] [{timestamp}] [{section}] {message}"
    elif message:
        console_msg = f"[{level}] [{timestamp}] {message}"
    elif section:
        console_msg = f"[{level}] [{timestamp}] {section}"
    else:
        return  # No hay nada que loggear

    # Enviar a stdout o stderr según el nivel
    if level.upper() == "ERROR":
        print(console_msg, file=sys.stderr, flush=True)
    else:
        print(console_msg, flush=True)

    # Manejo de archivo
    if file:
        try:
            os.makedirs(os.path.dirname(file), exist_ok=True)

            # Reset del log solo una vez por ejecución
            # with open(file, "a", encoding="utf-8") as f:
            #     f.write(
            #         f"{'=' * 20} NUEVA SESIÓN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {'=' * 20}\n"
            #     )

            # Logger ID único por archivo
            logger_id = f"log_custom_{abs(hash(file))}"

            if logger_id not in _loggers:
                logger = logging.getLogger(logger_id)
                logger.setLevel(logging.INFO)

                # Limpiar handlers duplicados
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)

                handler = logging.FileHandler(file, encoding="utf-8", mode="a")
                handler.setFormatter(
                    logging.Formatter("%(asctime)s - [%(levelname)s] %(message)s")
                )
                logger.addHandler(handler)
                logger.propagate = False

                _loggers[logger_id] = logger
            else:
                logger = _loggers[logger_id]

            if level.upper() == "INFO":
                logger.info(message)
            elif level.upper() == "WARNING":
                logger.warning(message)
            elif level.upper() == "ERROR":
                logger.error(message)

        except Exception as e:
            print(f"[ERROR] Error manejando log de archivo: {e}", file=sys.stderr, flush=True)


def main():
    if len(sys.argv) < 2:
        sys.exit("Error: Uso: python log.py <comando> [<args>]")

    comando = sys.argv[1]

    if comando == "log_custom":
        if len(sys.argv) < 4:
            sys.exit(
                "Error: Uso correcto: python log.py log_custom <section> <message> <level> [<file>]"
            )

        section = sys.argv[2]
        message = sys.argv[3]
        level = sys.argv[4] if len(sys.argv) > 4 else "INFO"
        file = sys.argv[5] if len(sys.argv) > 5 else None

        # Tratar "None" como None real
        section = None if section in ("None", "") else section
        message = None if message in ("None", "") else message

        log_custom(section, message, level, file)


if __name__ == "__main__":
    main()
