# Handoff — Bug : la capacité des arêtes est silencieusement ignorée par les poids Dijkstra sur MultiDiGraph (poids effectif = coût de saut seul) + correctif de performance validé

> **Statut** : handoff prêt à ouvrir en issue (les issues sont désactivées sur ce fork ;
> ouvrir sur `ainetus/ExpertOp4Grid` ou activer les issues ici).
> **Découvert le** : 2026-07-16, en écrivant un test d'équivalence pour un patch de
> performance de `_compute_sssp_paths` (benchmark RTE7000, voir Références).

## Résumé

Les fonctions de poids personnalisées passées aux Dijkstra de networkx dans la recherche de
lignes « null-flow » lisent les attributs d'arête via `attr.get("capacity", 0)`. Sur un
**multigraph** — et le graphe de surcharge est un `nx.MultiDiGraph` — networkx passe aux
callables de poids le **dict `{clé: attributs}` des arêtes parallèles**, pas le dict
d'attributs d'une arête. Le `.get("capacity", 0)` renvoie donc **toujours 0** :

- le poids de routage effectif est le **coût de saut seul** (33 promu / 100 normal) — le terme
  `capacity * HUGE_MULTIPLIER` n'a jamais contribué sur multigraph ;
- le garde de capacité négative (`raise ValueError`) est du code mort sur multigraph
  (la capacité n'est jamais lue).

## Code concerné

1. **`alphaDeesp/core/graphs/null_flow_graph.py`**, `NullFlowGraphMixin._compute_sssp_paths`
   (l. 427–463) : `incentivized_weight` (l. 439–444) — `real_weight = attr.get("capacity", 0)`
   vaut toujours `0` quand `g_c` est un multigraph, donc
   `nx.single_source_dijkstra_path(g_c, source, weight=incentivized_weight)` (l. 458) route
   uniquement sur les coûts de saut.

2. **`alphaDeesp/core/graphs/shortest_paths.py`**, `composite_weight` (l. 26–32) et ses appels
   `nx.dijkstra_path` (l. 39, 42, 126, 129, 219) : même motif. Le commentaire l. 27–28
   (« Handle MultiDiGraph: attr might be the inner dict … nx.dijkstra_path passes the edge
   attribute dictionary directly ») montre que l'ambiguïté avait été anticipée mais tranchée
   dans le mauvais sens pour les multigraphs.

## Cause racine

`_weight_function` de networkx (`networkx/algorithms/shortest_paths/weighted.py`) :

```python
def _weight_function(G, weight):
    if callable(weight):
        return weight                      # passé tel quel, SANS adaptation
    if G.is_multigraph():
        return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    return lambda u, v, data: data.get(weight, 1)
```

Pour un poids **chaîne** sur multigraph, networkx prend le min des attributs des arêtes
parallèles. Pour un **callable**, il transmet brut `G_succ[u][v]` — qui sur un multigraph est
`{clé: attributs}` — et c'est au callable d'itérer les clés. Les deux callables du dépôt le
traitent comme un dict d'attributs plat.

## Reproduction minimale

```python
import networkx as nx

g = nx.MultiDiGraph()
g.add_edge("A", "B", capacity=1.0);  g.add_edge("B", "C", capacity=2.0)
g.add_edge("A", "C", capacity=10.0)  # arête directe bien plus « lourde »

def incentivized_weight(u, v, attr):
    real_weight = attr.get("capacity", 0)   # attr est {0: {...}} -> toujours 0
    return real_weight * 1_000_000_000 + 100

print(nx.dijkstra_path(g, "A", "C", weight=incentivized_weight))
# ['A', 'C'] — l'arête de capacité 10 gagne : tous les poids se lisent en hop-only
```

Avec le poids voulu (capacité dominante), le plus court chemin serait `['A', 'B', 'C']`
(capacité 3 contre 10).

## Impact

- **Sémantique de routage** : la recherche de chemins des lignes null-flow (« quelles lignes
  déconnectées jalonnent un chemin court entre les côtés contraint et report ») sélectionne
  depuis l'adoption du multigraph des chemins **les plus courts en sauts**, pas pondérés par la
  capacité. Sur le benchmark RTE7000 (~6 400 nœuds, graphe de surcharge de 9 615 arêtes),
  l'ensemble des lignes retenues est plausiblement inchangé dans beaucoup d'instances (le
  filtre aval `_collect_paths_of_interest` est grossier : le chemin traverse ≥ 1 arête
  d'intérêt et fait ≤ `max_null_flow_path_length` nœuds), mais ce n'est pas garanti en général.
- **Performance** : c'est aussi le coût dominant hors load flow de la construction du graphe de
  surcharge à l'échelle nationale — des centaines de Dijkstra complets du graphe, chacun avec
  un callable Python invoqué à chaque relaxation d'arête (le mode de poids le plus lent de
  networkx). Profilé à ~90 % du temps hors LF de la construction du graphe sur RTE7000.

## Décision à prendre : entériner ou corriger

**Option A — entériner le comportement effectif** (hop-only sur multigraph) : le rendre
explicite et empocher un gros gain de perf — précalculer le coût de saut comme **attribut**
d'arête (une passe O(E)) et appeler Dijkstra avec un poids chaîne ; supprimer le terme
capacité mort et le garde. Sortie bit-à-bit identique à aujourd'hui.

**Option B — corriger le comportement voulu** (routage pondéré par la capacité) : lire la
capacité correctement sur multigraph (`min(a.get("capacity", 0) for a in attr.values())`
quand le mapping est à clés, ou précalculer un attribut `capacity*1e9 + hop` et utiliser un
poids chaîne). **Cela change le routage** et demande une validation des lignes null-flow
retenues sur des cas de référence. Note : sur un cas RTE7000, une expérience avec les poids
voulus a quand même produit un graphe de surcharge final identique (9 615 arêtes, 12 hubs) —
le filtre aval absorbe la différence là, mais c'est un point de donnée, pas une preuve.

## Correctif de performance validé (compatible avec les deux options)

Un patch appliqué à l'import, gardé en version, de `_compute_sssp_paths` est livré dans
`expert_op4grid_recommender` (branche `claude/expert-op4grid-performance-t1pdrq`,
`expert_op4grid_recommender/patched_alphadeesp.py`) en attendant le correctif upstream. Il
reproduit exactement le comportement effectif actuel (sémantique Option A sur multigraph) et
ajoute :

1. **Poids précalculé en attribut d'arête** (poids chaîne au lieu d'un callable Python) —
   supprime l'appel Python par relaxation ;
2. **Dijkstra inversé côté cibles** quand `|cibles| < |sources|` — écrase p. ex. un balayage de
   169 sources en 1 exécution (`_collect_paths_of_interest` ne consomme que
   `paths[source][target]`).

Mesuré sur RTE7000 (`automne_creux_2023` / contingence `ALBERL71BATHI`) :
`add_relevant_null_flow_lines_all_paths` **12,8 s → 9,4 s (−27 %)**, construction du graphe
36,8 s → 30,7 s, avec un **graphe de sortie bit-à-bit identique** (même SHA-256 de l'ensemble
trié des arêtes, mêmes 12 hubs). 9 tests unitaires couvrent application, idempotence,
équivalence avant/arrière et kill-switch (`tests/test_patched_alphadeesp.py`).

Marge restante après ce patch : un appel toutes-paires (179 sources × 179 cibles) domine le
coût résiduel. Suites candidates : exploration bornée en sauts (le consommateur jette tout
chemin de plus de `max_null_flow_path_length` nœuds, donc le balayage complet du graphe est du
travail perdu — nuance de comportement mineure à valider), mémoïsation entre les ~13 appels
par construction de graphe, et suppression des ~161 `MultiGraph.copy()` défensifs (~5 s).

## Références

- Benchmark + profilage + PoC : `marota/Grid_snapshot_reconstruct`, branche
  `claude/expert-op4grid-performance-t1pdrq`, `benchmarks/expert_op4grid_recommender/`
  (rapport §12.2/§12.4/§12.5 ; scripts `profile_alphadeesp.py`, `poc_dijkstra_opt.py`,
  `verify_pkg_patch.py`).
- Patch aval de transition : `marota/Expert_op4grid_recommender`, branche
  `claude/expert-op4grid-performance-t1pdrq`, commit `be2c7a8` (`patched_alphadeesp.py` — se
  désactive de lui-même si ce dépôt réécrit `_compute_sssp_paths`).
