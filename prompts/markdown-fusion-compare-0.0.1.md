Usando PySide6, crea una app que compare dos archivos Markdown de Obsidian.
Paneles y navegación
Debe tener dos paneles verticales. Las propiedades YAML se muestran ordenadas alfabéticamente en ambos lados, de forma que las mismas propiedades queden alineadas visualmente en la misma línea. No guardar los archivos hasta que el usuario lo decida; primero simular todos los cambios. Poner un botón "Volver a comparar" por si el usuario modificó algo directamente.
Propiedades YAML
Permitir leer cada ítem del YAML y copiarlo de un archivo al otro (bidireccional: izquierda→derecha y derecha→izquierda). Al hacer clic en una propiedad, mostrar un menú con las opciones: copiar, copiar agregando como ítem de lista, copiar como wikilink. Si los valores son iguales, ofrecer la opción de convertir a wikilink. También permitir convertir por lote todas las propiedades seleccionadas a wikilink. Cuando es una lista, el wikilink va entre comillas: "[[enlace]]".
Edición directa
Permitir al usuario editar los archivos de cualquier panel directamente, escribiendo o borrando.
Cuerpo de la nota
Permitir copiar el cuerpo de la nota, eligiendo si va al principio o al final. En ese caso, ignorar las líneas que ya existen en el archivo destino.
Plantillas
Permitir guardar como plantilla: genera un archivo .md con todas las propiedades en blanco.