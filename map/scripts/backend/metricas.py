import time
import json
import subprocess
import re
from datetime import datetime

class MetricasSimples:
    def __init__(self):
        self.inicio = time.time()
        self.inicio_dt = datetime.now()
        self.exitosas = 0
        self.fallidas = 0
        self.duplicadas = 0
        self.total_bytes = 0
        self.errores = []
        self.tamaños_archivos = []  # Para calcular peso promedio
        self.formatos = {}  # Para contar formatos: {'jpg': 45, 'tif': 23, 'png': 2}


        
    def registrar_exitosa(self, metadata=None, archivo_descargado=None):
        self.exitosas += 1
        
        # Usar solo tamaño real del archivo descargado
        tamaño_archivo = 0
        formato = "desconocido"
        
        if archivo_descargado:
            try:
                import os
                if os.path.exists(archivo_descargado):
                    # Obtener tamaño real del archivo
                    tamaño_archivo = os.path.getsize(archivo_descargado)
                    
                    # Detectar formato del archivo real
                    if archivo_descargado.lower().endswith(('.jpg', '.jpeg')):
                        formato = "JPG"
                    elif archivo_descargado.lower().endswith(('.tif', '.tiff')):
                        formato = "TIFF"
                    elif archivo_descargado.lower().endswith('.png'):
                        formato = "PNG"
                    else:
                        formato = "OTRO"
                else:
                    print(f" Archivo no encontrado para medir: {archivo_descargado}")
                    return  # No registrar si no existe el archivo
            except Exception as e:
                print(f" Error midiendo archivo {archivo_descargado}: {e}")
                return  # No registrar si hay error
        else:
            # Si no se proporciona ruta de archivo, detectar desde URL
            if metadata and "URL" in metadata:
                url = metadata["URL"]
                if url.lower().endswith(('.jpg', '.jpeg')):
                    formato = "JPG"
                elif url.lower().endswith(('.tif', '.tiff')):
                    formato = "TIFF"
                elif url.lower().endswith('.png'):
                    formato = "PNG"
            
            print(f" No se proporcionó ruta de archivo para medir tamaño real")
            return  # No registrar sin archivo real
        
        # Solo registrar si tenemos tamaño real
        if tamaño_archivo > 0:
            self.total_bytes += tamaño_archivo
            self.tamaños_archivos.append(tamaño_archivo)
            
            # Contar formatos
            if formato in self.formatos:
                self.formatos[formato] += 1
            else:
                self.formatos[formato] = 1
        
    def registrar_fallida(self, error=""):
        self.fallidas += 1
        if error:
            self.errores.append(error)
            
    def registrar_duplicada(self):
        self.duplicadas += 1
        
    def _calcular_eficiencia_red(self, velocidad_mb_s):
        """ELIMINADO - Ya no se usa"""
        return 0
        
    def obtener_reporte(self):
        tiempo_total = time.time() - self.inicio
        
        # Calcular peso promedio
        peso_promedio_mb = 0
        if self.tamaños_archivos:
            peso_promedio_bytes = sum(self.tamaños_archivos) / len(self.tamaños_archivos)
            peso_promedio_mb = peso_promedio_bytes / (1024 * 1024)
        
        # Encontrar formato predominante
        formato_predominante = "N/A"
        if self.formatos:
            formato_predominante = max(self.formatos, key=self.formatos.get)
            porcentaje_predominante = (self.formatos[formato_predominante] / sum(self.formatos.values())) * 100
            formato_predominante = f"{formato_predominante} ({porcentaje_predominante:.1f}%)"
        
        # Calcular velocidad
        velocidad_mb_s = (self.total_bytes/1024/1024)/tiempo_total if tiempo_total > 0 else 0
        
        return {
            "RESUMEN_EJECUTIVO": {
                "Inicio": self.inicio_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Duración_total": f"{tiempo_total/3600:.1f} horas" if tiempo_total > 3600 else f"{tiempo_total/60:.1f} minutos",
                "Imágenes_exitosas": self.exitosas,
                "Imágenes_fallidas": self.fallidas,
                "Imágenes_duplicadas": self.duplicadas,
                "Total_procesadas": self.exitosas + self.fallidas + self.duplicadas,
                "Tasa_éxito": f"{(self.exitosas/(self.exitosas+self.fallidas)*100):.1f}%" if (self.exitosas+self.fallidas) > 0 else "0%",
                "MB_descargados": f"{self.total_bytes/1024/1024:.1f} MB",
                "Peso_promedio_por_imagen": f"{peso_promedio_mb:.1f} MB",
                "Formato_predominante": formato_predominante,
                "Velocidad_promedio": f"{velocidad_mb_s:.1f} MB/s"
            },
            "DISTRIBUCION_FORMATOS": self.formatos,
            "ESTADISTICAS_TAMAÑO": {
                "Peso_mínimo_MB": f"{min(self.tamaños_archivos)/(1024*1024):.1f}" if self.tamaños_archivos else "0",
                "Peso_máximo_MB": f"{max(self.tamaños_archivos)/(1024*1024):.1f}" if self.tamaños_archivos else "0",
                "Peso_promedio_MB": f"{peso_promedio_mb:.1f}",
                "Total_archivos_medidos": len(self.tamaños_archivos)
            },
            "ERRORES": self.errores[:10]  # Solo primeros 10 errores
        }
        
    def mostrar_progreso(self, actual, total):
        """Muestra progreso simple cada 10 imágenes"""
        if actual % 10 == 0 or actual == total:
            porcentaje = (actual / total * 100) if total > 0 else 0
            tiempo_transcurrido = time.time() - self.inicio
            velocidad = (self.total_bytes/1024/1024) / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
            
            print(f" Progreso: {actual}/{total} ({porcentaje:.1f}%) - "
                  f"Exitosas: {self.exitosas} - Fallidas: {self.fallidas} - "
                  f"Velocidad: {velocidad:.1f} MB/s")
                  
    def guardar_reporte_final(self):
        """Guarda reporte final en JSON"""
        reporte = self.obtener_reporte()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_descarga_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
            
        # Mostrar resumen en consola
        print("\n" + "="*80)
        print(" REPORTE FINAL DE DESCARGA")
        print("="*80)
        resumen = reporte["RESUMEN_EJECUTIVO"]
        for key, value in resumen.items():
            print(f"{key.replace('_', ' ')}: {value}")
            
        print(f"\n DISTRIBUCIÓN DE FORMATOS:")
        for formato, cantidad in reporte["DISTRIBUCION_FORMATOS"].items():
            porcentaje = (cantidad / sum(reporte["DISTRIBUCION_FORMATOS"].values())) * 100
            print(f"   {formato}: {cantidad} imágenes ({porcentaje:.1f}%)")
            
        print(f"\n ESTADÍSTICAS DE TAMAÑO:")
        stats = reporte["ESTADISTICAS_TAMAÑO"]
        print(f"   Peso mínimo: {stats['Peso_mínimo_MB']} MB")
        print(f"   Peso máximo: {stats['Peso_máximo_MB']} MB")
        print(f"   Peso promedio: {stats['Peso_promedio_MB']} MB")
        
        print(f"\n Reporte guardado en: {filename}")
        print("="*80)
        
        return filename