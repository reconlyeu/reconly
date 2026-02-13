# Knowledge Graph

The knowledge graph visualizes connections between entities (people, organizations, topics, technologies) extracted from your digests. It helps you discover relationships and patterns across your content.

## Requirements

Entity extraction must be enabled for the knowledge graph to populate. See the [feature setup guide](../admin/feature-setup-guide.md) for configuration.

Once enabled, new feed runs automatically extract entities and their relationships.

## Navigating the Graph

Open **Knowledge Graph** in the sidebar to view the visualization.

The graph displays:
- **Nodes** — entities like people, organizations, locations, and topics
- **Edges** — connections between entities (mentioned together, related topics, etc.)
- **Clusters** — groups of closely related entities

### Interactions

- **Pan** — click and drag the background to move around
- **Zoom** — scroll wheel to zoom in/out
- **Select a node** — click to see entity details and related digest entries
- **Hover** — see the entity name and connection count

### Node Details

Clicking a node shows:
- Entity name and type
- How many times it appears across your digests
- List of digest entries that mention this entity
- Connected entities

## Growing the Graph

The graph becomes more useful as your digest collection grows:

- **Early stage** (< 50 digests) — sparse connections, individual entities
- **Growing** (50-500 digests) — clusters form around key topics and actors
- **Mature** (500+ digests) — rich interconnections reveal trends and patterns

## Tips

- **Focus on clusters** — tightly connected groups of entities often represent important themes in your content
- **Look for bridges** — entities connecting two otherwise separate clusters may represent cross-cutting trends
- **Use with chat** — when you spot an interesting entity in the graph, ask about it in Chat for a deeper summary
- **Check regularly** — the graph evolves as new content is processed, revealing emerging topics
