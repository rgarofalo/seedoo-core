import os
import json
from collections import defaultdict
from graphviz import Digraph


def load_manifest_dependencies(base_dir):
    """
    Legge tutti i file __manifest__.py all'interno di base_dir e crea un albero delle dipendenze.
    :param base_dir: Percorso alla directory di base da cui iniziare a cercare.
    :return: Dizionario con le cartelle e relative dipendenze.
    """
    dependencies_tree = defaultdict(list)

    for root, dirs, files in os.walk(base_dir):
        if "__manifest__.py" in files:
            manifest_path = os.path.join(root, "__manifest__.py")
            folder_name = os.path.basename(root)
            try:
                # Leggi il contenuto del file __manifest__.py
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Converti il contenuto del file in un dizionario JSON
                    manifest_data = eval(
                        content
                    )  # Usato eval perché spesso i file manifest sono Python-validi, non solo JSON
                    if "depends" in manifest_data:
                        filtered_dependencies = [
                                dep for dep in manifest_data["depends"] if dep.startswith(('fl_', 'sd_'))
                            ]
                        dependencies_tree[folder_name] = filtered_dependencies
            except Exception as e:
                print(f"Errore leggendo il file {manifest_path}: {e}")

    return dependencies_tree


def print_dependency_tree(dependencies_tree):
    """
    Stampa l'albero delle dipendenze in un formato leggibile.
    :param dependencies_tree: Dizionario delle dipendenze.
    """

    def print_recursive(node, visited, level=0):
        if node in visited:
            print("    " * level + f"{node} (ciclo rilevato)")
            return
        visited.add(node)
        print("    " * level + node)
        for dep in dependencies_tree.get(node, []):
            print_recursive(dep, visited, level + 1)
        visited.remove(node)

    print("Albero delle dipendenze:")
    for module in dependencies_tree:
        print_recursive(module, set())


def generate_dependency_graph(dependencies_tree, output_filename="dependency_graph"):
    """
    Genera un grafico delle dipendenze usando Graphviz.
    :param dependencies_tree: Dizionario delle dipendenze.
    :param output_filename: Nome del file di output per il grafico.
    """
    dot = Digraph(comment="Dependency Tree", format="png")

    # Aggiungi i nodi e gli archi al grafo
    for module, dependencies in dependencies_tree.items():
        dot.node(module, module)  # Aggiungi il nodo principale
        for dep in dependencies:
            dot.node(dep, dep)  # Aggiungi il nodo della dipendenza
            dot.edge(module, dep)  # Crea un arco tra il modulo e la sua dipendenza

    # Salva e renderizza il grafo
    dot.render(output_filename)
    print(f"Grafico generato: {output_filename}.png")


if __name__ == "__main__":
    # Imposta la directory di base da esplorare (sostituire con il tuo percorso)
    base_directory = "."  # Cambia con il percorso effettivo delle tue cartelle

    # Carica le dipendenze
    dependencies = load_manifest_dependencies(base_directory)

    # Stampa l'albero delle dipendenze
    # print_dependency_tree(dependencies)

    generate_dependency_graph(dependencies, "dependency_graph")
