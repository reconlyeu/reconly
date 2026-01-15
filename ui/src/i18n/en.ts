/**
 * English UI strings - externalized for i18n-ready architecture
 *
 * All user-facing strings should be defined here.
 * When adding i18n support later, create additional language files (de.ts, etc.)
 * and implement a language switching mechanism.
 */

export const strings = {
  // Application
  app: {
    name: 'Reconly',
    tagline: 'Privacy-First Research Intelligence',
  },

  // Navigation
  nav: {
    dashboard: 'Dashboard',
    digests: 'Digests',
    sources: 'Sources',
    feeds: 'Feeds',
    feedRuns: 'Feed Runs',
    templates: 'Templates',
    analytics: 'Analytics',
    knowledgeGraph: 'Knowledge Graph',
    settings: 'Settings',
  },

  // Dashboard
  dashboard: {
    title: 'Dashboard',
    stats: {
      sources: 'Sources',
      feeds: 'Feeds',
      digests: 'Digests',
      tokensToday: 'Tokens Today',
      tokensWeek: 'Tokens This Week',
      successRate: 'Success Rate',
    },
    recentRuns: 'Recent Feed Runs',
    recentDigests: 'Recent Digests',
    noRuns: 'No recent feed runs',
    noDigests: 'No recent digests',
  },

  // Sources
  sources: {
    title: 'Sources',
    addSource: 'Add Source',
    editSource: 'Edit Source',
    deleteSource: 'Delete Source',
    types: {
      all: 'All',
      rss: 'RSS',
      youtube: 'YouTube',
      website: 'Website',
      blog: 'Blog',
      imap: 'Email',
      agent: 'AI Agent',
    },
    fields: {
      name: 'Name',
      url: 'URL',
      type: 'Type',
      enabled: 'Enabled',
      maxItems: 'Max Items',
      fetchFullContent: 'Fetch Full Content',
      fetchTranscript: 'Fetch Transcript',
    },
    usedBy: 'Used by {count} feeds',
    confirmDelete: 'Are you sure you want to delete this source?',
  },

  // Feeds
  feeds: {
    title: 'Feeds',
    createFeed: 'Create Feed',
    editFeed: 'Edit Feed',
    deleteFeed: 'Delete Feed',
    runNow: 'Run Now',
    viewHistory: 'View History',
    fields: {
      name: 'Name',
      description: 'Description',
      sources: 'Sources',
      schedule: 'Schedule',
      promptTemplate: 'Prompt Template',
      reportTemplate: 'Report Template',
      outputs: 'Outputs',
    },
    schedulePresets: {
      hourly: 'Every hour',
      daily: 'Daily at midnight',
      twiceDaily: 'Twice daily',
      weekly: 'Weekly on Sunday',
      custom: 'Custom cron',
    },
    outputs: {
      database: 'Save to Database',
      email: 'Send via Email',
      obsidian: 'Export to Obsidian',
    },
    status: {
      lastRun: 'Last Run',
      nextRun: 'Next Run',
      never: 'Never',
    },
    confirmDelete: 'Are you sure you want to delete this feed?',
    runStarted: 'Feed run started',
  },

  // Feed Runs
  feedRuns: {
    title: 'Feed Runs',
    subtitle: 'View execution history and debug failed runs',
    viewAll: 'View All',
    viewDetails: 'View Details',
    filters: {
      allFeeds: 'All Feeds',
      allStatuses: 'All Statuses',
      fromDate: 'From Date',
      toDate: 'To Date',
      clearFilters: 'Clear Filters',
    },
    table: {
      feed: 'Feed',
      status: 'Status',
      sources: 'Sources',
      items: 'Items',
      tokens: 'Tokens',
      cost: 'Cost',
      duration: 'Duration',
      started: 'Started',
    },
    details: {
      title: 'Feed Run Details',
      overview: 'Overview',
      sources: 'Sources',
      errors: 'Errors',
      digests: 'Digests',
      metrics: 'Metrics',
      traceId: 'Trace ID',
      triggeredBy: 'Triggered By',
      noErrors: 'No errors occurred during this run',
      noDigests: 'No digests were created during this run',
    },
    noRuns: 'No feed runs found',
    errorTypes: {
      FetchError: 'Fetch Error',
      ParseError: 'Parse Error',
      SummarizeError: 'Summarize Error',
      SaveError: 'Save Error',
      TimeoutError: 'Timeout',
    },
  },

  // Agent Runs
  agentRuns: {
    title: 'Agent Run History',
    noRuns: 'No agent runs yet',
    noRunsDescription: 'This agent source hasn\'t been run yet. Add it to a feed and run the feed to see results here.',
    refresh: 'Refresh',
    details: {
      title: 'Agent Run Details',
      prompt: 'Research Prompt',
      toolCalls: 'Tool Calls',
      sourcesConsulted: 'Sources Consulted',
      result: 'Result',
      errorLog: 'Error Log',
    },
    stats: {
      duration: 'Duration',
      iterations: 'Iterations',
      tokens: 'Tokens',
      cost: 'Est. Cost',
    },
  },

  // Templates
  templates: {
    title: 'Templates',
    tabs: {
      prompt: 'Prompt Templates',
      report: 'Report Templates',
    },
    createTemplate: 'Create Template',
    editTemplate: 'Edit Template',
    deleteTemplate: 'Delete Template',
    duplicateTemplate: 'Duplicate',
    systemTemplate: 'System Template',
    userTemplate: 'User Template',
    fields: {
      name: 'Name',
      description: 'Description',
      language: 'Language',
      targetLength: 'Target Length',
      format: 'Format',
      systemPrompt: 'System Prompt',
      userPrompt: 'User Prompt',
      template: 'Template',
    },
    preview: 'Preview',
    usedBy: 'Used by {count} feeds',
    confirmDelete: 'Are you sure you want to delete this template?',
  },

  // Knowledge Graph
  knowledgeGraph: {
    title: 'Knowledge Graph',
    subtitle: 'Explore relationships between your digests, tags, and sources',
    loading: 'Loading graph...',
    noData: 'No data to display',
    noDataDescription: 'Create some digests first, then explore their relationships here.',
    // Node types
    nodeTypes: {
      digest: 'Digest',
      tag: 'Tag',
      source: 'Source',
      feed: 'Feed',
    },
    // Edge types
    edgeTypes: {
      semantic: 'Semantic',
      tag: 'Tag',
      source: 'Source',
      temporal: 'Temporal',
    },
    // Layouts
    layouts: {
      force: 'Force-Directed',
      hierarchical: 'Hierarchical',
      radial: 'Radial',
    },
    // Controls
    controls: {
      layout: 'Layout',
      viewMode: 'View',
      depth: 'Depth',
      minSimilarity: 'Min Similarity',
      includeTags: 'Include Tags',
      filters: 'Filters',
      zoomIn: 'Zoom In',
      zoomOut: 'Zoom Out',
      fitToScreen: 'Fit to Screen',
      resetView: 'Reset View',
      exportPng: 'Export PNG',
      exportJson: 'Export JSON',
    },
    // Filters
    filters: {
      feed: 'Feed',
      dateRange: 'Date Range',
      fromDate: 'From',
      toDate: 'To',
      tags: 'Tags',
      allFeeds: 'All Feeds',
      clearFilters: 'Clear Filters',
    },
    // Sidebar
    sidebar: {
      details: 'Details',
      noSelection: 'Select a node to see details',
      published: 'Published',
      source: 'Source',
      feed: 'Feed',
      tags: 'Tags',
      relatedDigests: 'Related Digests',
      viewDigest: 'View Digest',
      expandNode: 'Expand Connections',
    },
    // Stats
    stats: {
      nodes: 'Nodes',
      edges: 'Edges',
      clusters: 'Clusters',
    },
  },

  // Digests
  digests: {
    title: 'Digests',
    search: 'Search digests...',
    filters: {
      feed: 'Filter by Feed',
      source: 'Filter by Source',
      tag: 'Filter by Tag',
      allFeeds: 'All Feeds',
      allSources: 'All Sources',
      allTags: 'All Tags',
    },
    export: 'Export',
    exportFormats: {
      json: 'JSON',
      csv: 'CSV',
      obsidian: 'Obsidian',
    },
    deleteDigest: 'Delete Digest',
    confirmDelete: 'Are you sure you want to delete this digest?',
    noDigests: 'No digests found',
  },

  // Analytics
  analytics: {
    title: 'Analytics',
    periods: {
      week: 'Last 7 days',
      month: 'Last 30 days',
      quarter: 'Last 90 days',
    },
    summary: {
      tokensIn: 'Tokens In',
      tokensOut: 'Tokens Out',
      successRate: 'Success Rate',
    },
    byProvider: 'Tokens by Provider',
    byFeed: 'Tokens by Feed',
    overTime: 'Usage Over Time',
    export: 'Export Data',
  },

  // Settings
  settings: {
    title: 'Settings',
    tabs: {
      providers: 'Providers',
      email: 'Email',
      exports: 'Exporters',
      fetchers: 'Fetchers',
      extensions: 'Extensions',
    },
    fetchers: {
      title: 'Fetchers',
      description: 'Configure content fetchers for retrieving articles, videos, and web pages.',
      configure: 'Configure',
      status: {
        active: 'Active',
        needsConfig: 'Needs Config',
        disabled: 'Disabled',
      },
    },
    providers: {
      title: 'LLM Providers',
      description: 'Provider configuration is managed via environment variables.',
      status: {
        available: 'Available',
        configured: 'Configured',
        notConfigured: 'Not Configured',
      },
      defaultProvider: 'Default Provider',
      defaultModel: 'Default Model',
      fallbackOrder: 'Fallback Order',
      viewDocs: 'View Documentation',
      models: 'Available Models',
    },
    email: {
      title: 'Email Settings',
      fields: {
        smtpHost: 'SMTP Host',
        smtpPort: 'SMTP Port',
        username: 'Username',
        password: 'Password',
        fromAddress: 'From Address',
      },
      testConnection: 'Test Connection',
      testSuccess: 'Connection successful',
      testFailed: 'Connection failed',
    },
    exports: {
      title: 'Export Settings',
      defaultFormat: 'Export Configuration',
      defaultFormatDescription: 'Select an export format to configure its settings',
      includeMetadata: 'Include Metadata',
      includeMetadataDescription: 'Include timestamps, provider info, and tags in exports',
      configuration: '{name} Configuration',
      configurationDescription: 'Configure settings for the {name} exporter',
      noConfigNeeded: 'No additional configuration needed for {name} export.',
      directExport: 'Export to {name}',
      directExportDescription: 'Export all digests directly to your configured path',
      targetPath: 'Target Path',
      noPathConfigured: 'No export path configured',
      noPathConfiguredDescription: 'Configure the vault/export path in the exporter settings above to enable direct export.',
      exportButton: 'Export All Digests to {name}',
      exporting: 'Exporting...',
      exportSuccess: 'Exported {count} files to {path}',
      exportEmpty: 'No digests to export',
      exportError: 'Export failed',
      formats: {
        json: 'JSON',
        csv: 'CSV',
        obsidian: 'Obsidian Markdown',
        markdown: 'Markdown',
      },
      features: {
        directExport: 'Direct Export',
        configurable: 'Configurable',
      },
      obsidian: {
        title: 'Obsidian Export',
        vaultPath: 'Vault Path',
        vaultPathDescription: 'Path to your Obsidian vault',
        subfolder: 'Subfolder',
        subfolderDescription: 'Subfolder within the vault for digests',
        filenamePattern: 'Filename Pattern',
        filenamePatternDescription: 'Pattern for filenames. Variables: {title}, {date}, {id}',
        oneFilePerDigest: 'One File Per Digest',
        oneFilePerDigestDescription: 'Create separate files for each digest',
      },
    },
    save: 'Save Settings',
    saved: 'Settings saved',
    extensions: {
      title: 'Extensions',
      description: 'Installed extensions add new exporters, fetchers, and providers.',
      noExtensions: 'No Extensions Installed',
      noExtensionsDescription: 'Extensions can be installed via pip. Example:',
      installHint: 'pip install reconly-ext-<name>',
      status: {
        active: 'Active',
        needsConfig: 'Needs Config',
        disabled: 'Disabled',
        loadError: 'Load Error',
      },
      version: 'v{version}',
      author: 'by {author}',
      homepage: 'Homepage',
      configure: 'Configure',
      enable: 'Enable',
      disable: 'Disable',
      // Catalog (Phase 2)
      browseCatalog: 'Browse Catalog',
      catalog: {
        title: 'Extension Catalog',
        description: 'Discover and install community extensions.',
        search: 'Search extensions...',
        filterType: 'Filter by type',
        allTypes: 'All types',
        verifiedOnly: 'Verified only',
        verified: 'Verified',
        installed: 'Installed',
        install: 'Install',
        installing: 'Installing...',
        uninstall: 'Uninstall',
        uninstalling: 'Uninstalling...',
        upgrade: 'Upgrade',
        restartRequired: 'Restart required for changes to take effect',
        installSuccess: '{name} installed successfully',
        installFailed: 'Failed to install {name}',
        uninstallSuccess: '{name} uninstalled successfully',
        uninstallFailed: 'Failed to uninstall {name}',
        noResults: 'No extensions found',
        noResultsDescription: 'Try a different search term or filter.',
        loading: 'Loading catalog...',
        error: 'Failed to load catalog',
      },
    },
  },

  // Common
  common: {
    loading: 'Loading...',
    error: 'An error occurred',
    retry: 'Retry',
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    create: 'Create',
    close: 'Close',
    confirm: 'Confirm',
    search: 'Search',
    filter: 'Filter',
    export: 'Export',
    import: 'Import',
    enabled: 'Enabled',
    disabled: 'Disabled',
    yes: 'Yes',
    no: 'No',
    none: 'None',
    all: 'All',
    noResults: 'No results found',
    darkMode: 'Dark Mode',
    lightMode: 'Light Mode',
  },

  // Status
  status: {
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed',
  },

  // Errors
  errors: {
    generic: 'Something went wrong. Please try again.',
    network: 'Network error. Please check your connection.',
    notFound: 'The requested resource was not found.',
    validation: 'Please check your input and try again.',
    unauthorized: 'You are not authorized to perform this action.',
  },

  // Time
  time: {
    justNow: 'Just now',
    minutesAgo: '{count} minutes ago',
    hoursAgo: '{count} hours ago',
    daysAgo: '{count} days ago',
    never: 'Never',
  },
} as const;

export type Strings = typeof strings;
