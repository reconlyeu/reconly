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

  // Demo mode
  demo: {
    bannerFull: "You're exploring Reconly in demo mode with sample data.",
    bannerShort: 'Demo mode with sample data.',
    learnMore: 'Learn how to set up your own instance',
    dismiss: 'Dismiss demo mode banner',
    mode: 'Demo Mode',
  },

  // Navigation
  nav: {
    dashboard: 'Dashboard',
    digests: 'Digests',
    sources: 'Sources',
    feeds: 'Feeds',
    feedRuns: 'Feed Runs',
    templates: 'Templates',
    chat: 'Chat',
    analytics: 'Analytics',
    knowledgeGraph: 'Knowledge Graph',
    settings: 'Settings',
    logout: 'Logout',
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
    recentFeeds: {
      title: 'Recent Feeds',
      noFeeds: 'No feeds run recently',
      active: 'Active',
      paused: 'Paused',
      noSchedule: 'No schedule',
      source: 'source',
      sources: 'sources',
    },
    noRuns: 'No recent feed runs',
    noDigests: 'No recent digests',
    digestFilters: {
      today: 'Today',
      thisWeek: 'This Week',
      all: 'All',
    },
  },

  // Quick Insights (Dashboard)
  quickInsights: {
    newToday: 'New Today',
    thisWeek: 'This Week',
    feedHealth: 'Feed Health',
    allHealthy: 'healthy',
    needsAttention: 'need attention',
  },

  // Quick Actions (Dashboard)
  quickActions: {
    chat: 'Chat',
    runFeeds: 'Run Feeds',
    runningFeeds: 'Running...',
    addSource: 'Add Source',
    runAllSuccess: 'Started {count} feeds successfully',
    runAllPartial: 'Started {succeeded} of {total} feeds',
    runAllError: 'Failed to run feeds',
    noFeedsToRun: 'No enabled feeds to run',
  },

  // Sources
  sources: {
    title: 'Sources',
    addSource: 'Add Source',
    editSource: 'Edit Source',
    deleteSource: 'Delete Source',
    status: {
      active: 'Active',
      disabled: 'Disabled',
    },
    actions: {
      toggle: 'Toggle source',
      edit: 'Edit source',
      delete: 'Delete source',
      openUrl: 'Open URL',
    },
    table: {
      name: 'Name',
      type: 'Type',
      url: 'URL',
      status: 'Status',
      actions: 'Actions',
    },
    empty: {
      title: 'No sources found',
      noSourcesYet: 'No sources yet. Create your first source to get started.',
      noTypeSourcesFound: 'No {type} sources found.',
    },
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
      maxItemsPerRun: 'Max Items per Run',
      fetchFullContent: 'Fetch Full Content',
      fetchTranscript: 'Fetch Transcript',
      includeKeywords: 'Include Keywords',
      excludeKeywords: 'Exclude Keywords',
      searchIn: 'Search In',
      enableSource: 'Enable Source',
    },
    placeholders: {
      name: 'Source name',
      noLimit: 'No limit',
      addKeyword: 'Add keyword...',
    },
    // Form sections and labels
    form: {
      addNewSource: 'Add New Source',
      filters: 'Filters',
      active: 'active',
      show: 'Show',
      hide: 'Hide',
      regex: 'Regex',
      disabledSourcesNotFetched: 'Disabled sources will not be fetched',
    },
    // Filter mode options
    filterModes: {
      both: 'Title & Content',
      titleOnly: 'Title Only',
      content: 'Content Only',
    },
    // Filter hints
    filterHints: {
      maxItems: 'Limit the number of items fetched per run (newest first)',
      includeKeywords: 'Items must match at least one keyword to be processed',
      excludeKeywords: 'Items matching any keyword will be skipped',
    },
    // Source type options
    typeOptions: {
      rss: 'RSS Feed',
      youtube: 'YouTube',
      website: 'Website',
      blog: 'Blog',
      imap: 'Email (IMAP)',
      agent: 'AI Research Agent',
    },
    // YouTube helper
    youtubeHelper: 'Supports both video URLs (youtube.com/watch?v=...) and channel URLs (youtube.com/@channel, youtube.com/channel/UC...). Channels will fetch transcripts from recent videos.',
    usedBy: 'Used by {count} feeds',
    confirmDelete: 'Are you sure you want to delete this source?',
    // Agent source form
    agent: {
      fields: {
        researchTopic: 'Research Topic',
        researchStrategy: 'Research Strategy',
        maxIterations: 'Max Research Iterations',
        searchProvider: 'Search Provider',
        reportFormat: 'Report Format',
        maxSubtopics: 'Max Subtopics',
      },
      hints: {
        researchTopic: 'Describe what the AI agent should research. Be specific for better results.',
        researchStrategy: 'Choose how thoroughly the agent should research the topic',
        maxIterations: 'How many search and fetch cycles the agent can perform (default: 5)',
        searchProvider: 'Override the global search provider for this source (optional)',
        reportFormat: 'Citation style for the research report',
        maxSubtopics: 'Maximum number of subtopics to explore (1-10)',
      },
      placeholders: {
        prompt: 'Research the latest developments in AI language models...',
      },
      strategies: {
        simple: 'Simple',
        comprehensive: 'Comprehensive',
        deep: 'Deep',
      },
      strategyDescriptions: {
        simple: 'Quick lookup using search and summarization',
        comprehensive: 'Multi-step research with subtopic exploration',
        deep: 'Exhaustive analysis with detailed research plan',
      },
      advancedOptions: 'Advanced Options',
      unavailable: 'Unavailable',
      defaultOption: 'Default',
      searchProviders: {
        default: 'Default (global setting)',
        duckduckgo: 'DuckDuckGo (free, no API key)',
        searxng: 'SearXNG (self-hosted)',
        tavily: 'Tavily (AI-optimized, requires API key)',
      },
      providerHints: {
        tavily: 'Note: Requires TAVILY_API_KEY environment variable',
        searxng: 'Note: Requires SearXNG instance configured via SEARXNG_URL',
      },
      gptResearcherWarning: {
        title: 'GPT Researcher not installed',
        message: 'Comprehensive and Deep strategies require the gpt-researcher package.',
        installHint: 'Install with:',
      },
      errors: {
        loadCapabilities: 'Could not load agent capabilities',
      },
      usingDefaultOptions: 'Using default options',
    },
    // IMAP source form
    imap: {
      fields: {
        provider: 'Email Provider',
        host: 'IMAP Server',
        port: 'Port',
        ssl: 'SSL/TLS',
        username: 'Username',
        password: 'Password',
        folders: 'Folders',
        senderFilter: 'Sender Filter',
        subjectFilter: 'Subject Filter',
      },
      placeholders: {
        host: 'imap.example.com',
        username: 'user@example.com',
        password: 'Enter password',
        folders: 'INBOX, Newsletters',
        senderFilter: '@newsletter.com',
        subjectFilter: 'Weekly Report',
      },
      hints: {
        folders: 'Comma-separated. Leave empty for INBOX only.',
        passwordEncrypted: 'Encrypted before storage.',
      },
      providers: {
        gmail: 'Gmail',
        outlook: 'Outlook',
        generic: 'IMAP',
      },
      providerDescriptions: {
        gmail: 'Connect using Google OAuth. Supports personal and Google Workspace accounts.',
        outlook: 'Connect using Microsoft OAuth. Supports Outlook.com and Microsoft 365 accounts.',
        generic: 'Connect to any IMAP server using traditional credentials.',
      },
      sections: {
        serverSettings: 'Server Settings',
        emailFilters: 'Email Filters',
      },
      configured: 'configured',
      oauthNotConfigured: 'OAuth providers not configured',
      oauth: {
        title: 'Secure OAuth Authentication',
        message: 'After creating this source, you\'ll be redirected to {provider} to authorize access. Your password is never stored - we use secure OAuth tokens.',
      },
    },
  },

  // Feeds
  feeds: {
    title: 'Feeds',
    createFeed: 'Create Feed',
    createNewFeed: 'Create New Feed',
    editFeed: 'Edit Feed',
    deleteFeed: 'Delete Feed',
    runNow: 'Run Now',
    running: 'Running...',
    viewHistory: 'View History',
    importBundle: 'Import Bundle',
    exportBundle: 'Export Bundle',
    fields: {
      name: 'Name',
      feedName: 'Feed Name',
      description: 'Description',
      sources: 'Sources',
      schedule: 'Schedule',
      promptTemplate: 'Prompt Template',
      reportTemplate: 'Report Template',
      outputs: 'Outputs',
      cronExpression: 'Cron Expression',
      emailRecipients: 'Email Recipients',
      webhookUrl: 'Webhook URL',
      customPath: 'Custom Path',
    },
    placeholders: {
      name: 'Feed name',
      description: 'Optional description',
      searchSources: 'Search sources...',
      cron: '0 9 * * *',
      emailRecipients: 'email@example.com',
      webhookUrl: 'https://...',
      overridePath: 'Override path (optional)',
      noGlobalPath: 'No global path configured',
    },
    // Form sections
    sections: {
      basicInformation: 'Basic Information',
      selectSources: 'Select Sources',
      schedule: 'Schedule',
      outputConfiguration: 'Output Configuration',
      autoExport: 'Auto-Export',
    },
    // Digest mode
    digestMode: {
      title: 'Digest Mode',
      individual: 'Individual',
      individualDescription: 'One digest per item (default)',
      perSource: 'Per Source',
      perSourceDescription: 'One digest per source',
      allSources: 'Single Briefing',
      allSourcesDescription: 'One digest for all sources',
      explanation: '<strong>Individual:</strong> One summary per item. <strong>Per Source:</strong> Consolidate items from each source. <strong>Single Briefing:</strong> Cross-source synthesis into one unified digest.',
    },
    // Template options
    templateOptions: {
      selectTemplate: 'Select template...',
      systemTemplates: 'System Templates',
      userTemplates: 'User Templates',
    },
    // Cron help
    cronHelp: {
      title: 'Cron Syntax (5 fields)',
      syntax: 'minute hour day month weekday',
      examples: {
        daily9am: 'Daily 9 AM',
        weekdays8am: 'Weekdays 8 AM',
        every6hours: 'Every 6 hours',
        monday730am: 'Monday 7:30 AM',
      },
    },
    // Auto export
    autoExport: {
      description: 'Automatically export digests to configured destinations after each feed run completes.',
      noPathWarning: 'No export path configured. Set a path below or configure the global path in',
      settingsExport: 'Settings → Export',
      noExportersEnabled: 'No exporters are enabled. Enable exporters in',
      toConfigureAutoExport: 'to configure auto-export.',
      disabledExportersWarning: 'Some configured exporters are now disabled:',
      enableInSettings: 'Enable them in',
      toUseAgain: 'to use them again.',
      leaveEmptyForGlobal: 'leave empty to use global:',
      optionalOverride: 'optional override',
    },
    // Source selection
    sourceSelection: {
      selected: '{count} selected',
      disabled: 'Disabled',
      noSourcesFound: 'No sources found',
      disabledSourcesWarning: '{count} disabled source(s) selected. Disabled sources will be skipped during feed runs.',
    },
    // Hints
    hints: {
      commaSeparatedEmails: 'Comma-separated email addresses',
    },
    schedulePresets: {
      hourly: 'Every hour',
      daily: 'Daily at midnight',
      twiceDaily: 'Twice daily',
      weekly: 'Weekly on Sunday',
      custom: 'Custom cron',
      noSchedule: 'No schedule',
      noScheduleSet: 'No schedule set',
    },
    outputs: {
      database: 'Save to Database',
      email: 'Send via Email',
      obsidian: 'Export to Obsidian',
    },
    status: {
      active: 'Active',
      paused: 'Paused',
      lastRun: 'Last Run',
      nextRun: 'Next Run',
      never: 'Never',
      neverRun: 'Never run',
      completed: 'Completed',
      completedWithErrors: 'Partial',
      failed: 'Failed',
    },
    table: {
      name: 'Name',
      sources: 'Sources',
      schedule: 'Schedule',
      lastRun: 'Last Run',
      status: 'Status',
      actions: 'Actions',
    },
    actions: {
      runFeedNow: 'Run feed now',
      toggleFeedSchedule: 'Toggle feed schedule',
      editFeed: 'Edit feed',
      deleteFeed: 'Delete feed',
      exportFeedBundle: 'Export feed bundle',
      saving: 'Saving...',
      updateFeed: 'Update Feed',
    },
    sourceUnit: 'source',
    sourcesUnit: 'sources',
    assigned: 'assigned',
    empty: {
      title: 'No feeds configured',
      message: 'Create your first feed to start orchestrating content from your sources.',
    },
    confirmDelete: 'Are you sure you want to delete this feed?',
    runStarted: 'Feed run started',
    // Import bundle modal
    import: {
      title: 'Import Feed Bundle',
      description: 'Upload a feed bundle JSON file to import a pre-configured feed with sources and templates.',
      dropZone: {
        title: 'Drop your bundle file here',
        subtitle: 'or click to browse',
      },
      validating: 'Validating bundle...',
      importing: 'Importing feed bundle...',
      errors: {
        selectJson: 'Please select a JSON file',
        invalidJson: 'Invalid JSON file. Please ensure the file is a valid feed bundle.',
        title: 'Error',
      },
      preview: {
        errors: 'Errors',
        warnings: 'Warnings',
        feedExists: {
          title: 'Feed Already Exists',
          message: 'A feed with the name "{name}" already exists. Please rename or delete it before importing.',
        },
        willBeCreated: 'Will be created',
        sources: 'Sources',
        promptTemplate: 'Prompt Template',
        reportTemplate: 'Report Template',
        schedule: 'Schedule',
        new: 'new',
        existing: 'existing',
        none: 'None',
      },
      actions: {
        back: 'Back',
        import: 'Import Feed',
      },
      success: 'Feed "{name}" imported successfully',
      failed: 'Import failed: {error}',
    },
  },

  // Feed Runs
  feedRuns: {
    title: 'Feed Runs',
    subtitle: 'View execution history and debug failed runs',
    viewAll: 'View All',
    viewDetails: 'View Details',
    backToFeedRuns: 'Back to Feed Runs',
    noIdSpecified: 'No feed run ID specified.',
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
      runInformation: 'Run Information',
      timing: 'Timing',
      duration: 'Duration',
      items: 'Items',
      tokens: 'Tokens',
      created: 'Created',
      started: 'Started',
      completed: 'Completed',
      llmProvider: 'LLM Provider',
      llmModel: 'LLM Model',
      failed: 'failed',
      tokensIn: 'In:',
      tokensOut: 'Out:',
      runNumber: 'Run #{id}',
      triggeredByLabel: 'Triggered by {trigger}',
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
    runs: 'runs',
    failedToLoad: 'Failed to load agent runs. Please try again.',
    details: {
      title: 'Agent Run Details',
      prompt: 'Research Prompt',
      toolCalls: 'Tool Calls',
      sourcesConsulted: 'Sources Consulted',
      result: 'Result',
      errorLog: 'Error Log',
      subtopics: 'Subtopics',
      researchPlan: 'Research Plan',
      reportFormat: 'Report Format:',
      traceId: 'Trace ID:',
      created: 'Created:',
      started: 'Started:',
      completed: 'Completed:',
      input: 'Input:',
      output: 'Output:',
    },
    stats: {
      duration: 'Duration',
      iterations: 'Iterations',
      tokens: 'Tokens',
      cost: 'Est. Cost',
      sources: 'Sources',
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
    // Form-specific labels
    createPromptTemplate: 'Create Prompt Template',
    editPromptTemplate: 'Edit Prompt Template',
    createReportTemplate: 'Create Report Template',
    editReportTemplate: 'Edit Report Template',
    templateName: 'Template Name',
    templateContent: 'Template Content',
    jinja2TemplateContent: 'Jinja2 Template Content',
    outputFormat: 'Output Format',
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
    placeholders: {
      name: 'Brief Tech Summary',
      reportName: 'Clean Markdown Report',
      description: 'Concise technical summaries for developers',
      reportDescription: 'Clean markdown format suitable for email and documentation',
    },
    // Target length options
    targetLengths: {
      brief: 'Brief (~100 words)',
      standard: 'Standard (~150 words)',
      detailed: 'Detailed (~300 words)',
      comprehensive: 'Comprehensive (~500 words)',
    },
    // Format options
    formats: {
      markdown: 'Markdown (.md)',
      html: 'HTML (.html)',
      text: 'Plain Text (.txt)',
    },
    // Origin badges
    origin: {
      builtin: 'Built-in',
      imported: 'Imported',
      custom: 'Custom',
    },
    // Type labels
    types: {
      prompt: 'Prompt Template',
      report: 'Report Template',
    },
    // Status
    status: {
      active: 'Active',
      inactive: 'Inactive',
    },
    // Section headers
    sections: {
      systemTemplates: 'System Templates',
      userTemplates: 'User Templates',
    },
    // Empty states
    empty: {
      noSystemTemplates: 'No system templates',
      systemTemplatesMessage: 'System templates will be available after initialization.',
      noUserTemplates: 'No user templates yet',
      promptTemplatesMessage: 'Create your first prompt template to customize content summarization',
      reportTemplatesMessage: 'Create your first report template to customize digest formatting',
    },
    // Actions
    actions: {
      createCopy: 'Create a Copy',
      editTemplate: 'Edit template',
      deleteTemplate: 'Delete template',
      enableTemplate: 'Enable template',
      disableTemplate: 'Disable template',
    },
    // Hints
    hints: {
      templateVariables: 'Use {language}, {target_length}, and {content} as variables',
      jinja2Syntax: 'Use Jinja2 syntax with variables like {{ digest.title }}, {{ digest.summary }}, and {% for %} loops',
    },
    // Meta text
    meta: {
      words: '~{count} words',
      noSettings: 'No settings',
      noFormat: 'No format',
    },
    // Button labels
    saving: 'Saving...',
    updateTemplate: 'Update Template',
    preview: 'Preview',
    usedBy: 'Used by {count} feeds',
    confirmDelete: 'Are you sure you want to delete this template?',
    // Table columns
    table: {
      name: 'Name',
      category: 'Category',
      language: 'Language',
      format: 'Format',
      description: 'Description',
      status: 'Status',
      actions: 'Actions',
    },
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
      relationshipTypes: 'Relationship Types',
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
    // Card labels
    card: {
      viewOriginal: 'View original',
      deleteDigest: 'Delete digest',
      article: 'article',
    },
    // List labels
    list: {
      emptyTitle: 'No digests found',
      noFiltersMessage: 'Digests will appear here once feeds start running',
      filterMessage: 'Try adjusting your filters or search query',
    },
    // Modal labels
    modal: {
      published: 'Published:',
      tokens: 'tokens',
      summaryTitle: 'Summary',
      fullContentTitle: 'Full Content',
      tagsTitle: 'Tags',
      noTagsYet: 'No tags yet. Click Edit to add tags.',
      addTagsPlaceholder: 'Add tags...',
    },
    // Table labels
    table: {
      title: 'Title',
      type: 'Type',
      provider: 'Provider',
      tags: 'Tags',
      date: 'Date',
      actions: 'Actions',
      untitled: 'Untitled',
      viewDigest: 'View digest',
      deleteDigest: 'Delete digest',
    },
    // Source types
    sourceTypes: {
      youtube: 'YouTube',
      rss: 'RSS Feed',
      website: 'Website',
      blog: 'Blog',
      imap: 'Email',
      agent: 'AI Research',
    },
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
    // Provider chart
    providerChart: {
      title: 'Tokens by Provider',
      failedToLoad: 'Failed to load provider data',
      noData: 'No provider usage data available',
      tokens: 'tokens',
      models: 'models',
      totalUsage: 'Total Usage',
    },
    // Usage over time chart
    usageChart: {
      title: 'Cumulative Token Usage',
      failedToLoad: 'Failed to load usage data',
      noData: 'No usage data available for this period',
      cumulative: 'Cumulative',
      total: 'Total:',
      in: 'In:',
      out: 'Out:',
      thisDay: 'This Day',
      daily: 'Daily:',
    },
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
      contentFetchers: 'Content Fetchers',
      selectFetcher: 'Select a fetcher to configure its settings',
      noFetchers: 'No fetchers available',
      noFetchersDescription: 'Content fetchers will appear here once they are registered.',
      checkInstallation: 'Check your installation or contact support if fetchers are missing.',
      fetcher: 'Fetcher',
      extension: 'Extension',
      configureRequired: 'Configure required fields first',
      disableFetcher: 'Disable fetcher',
      enableFetcher: 'Enable fetcher',
      noConfigNeeded: 'No additional configuration needed for {name} fetcher.',
      settingsSaved: '{name} settings saved',
      status: {
        active: 'Active',
        needsConfig: 'Needs Config',
        disabled: 'Disabled',
      },
    },
    providers: {
      title: 'LLM Providers',
      description: 'Provider configuration is managed via environment variables.',
      fallbackChain: 'LLM Fallback Chain',
      fallbackChainDescription: 'Drag to reorder. First available provider will be used.',
      noProvidersInChain: 'No providers in chain. Add a provider to get started.',
      add: 'Add',
      ready: 'Ready',
      notReady: 'Not Ready',
      saveOrder: 'Save Order',
      refresh: 'Refresh',
      refreshStatus: 'Refresh provider status and models',
      statusRefreshed: 'Provider status refreshed',
      local: 'Local',
      cloud: 'Cloud',
      configureProvider: 'Configure provider',
      removeFromChain: 'Remove from chain',
      fallbackChainSaved: 'Fallback chain saved',
      failedToLoadProviders: 'Failed to load providers',
      // Embedding settings
      embedding: {
        title: 'Embedding',
        description: 'For RAG & semantic search',
        provider: 'Provider',
        model: 'Model',
        dimension: 'Dimension',
        source: 'Source',
        warning: 'Changing embedding model requires re-embedding all content. Configure via',
        and: 'and',
        inEnvFile: 'in your .env file.',
      },
      // Environment configuration info
      envConfig: {
        title: 'Environment Configuration',
        description: 'API keys and embedding settings must be configured via environment variables in your',
        file: 'file. Click the gear icon on a provider to configure its default model.',
      },
      // Provider config panel
      configPanel: {
        configuration: '{name} Configuration',
        configureSettings: 'Configure settings for {name}',
        envVariables: 'Environment Variables',
        envVariablesDescription: 'The following settings are configured via environment variables and cannot be changed here:',
        noConfigNeeded: 'No additional configuration needed for this provider.',
        configureApiKey: 'Configure API key via environment variables to enable this provider.',
        selectModel: 'Select {label}...',
        settingsSaved: '{name} settings saved',
      },
      status: {
        available: 'Available',
        configured: 'Configured',
        notConfigured: 'Not Configured',
        unavailable: 'Not Running',
      },
      defaultProvider: 'Default Provider',
      defaultModel: 'Default Model',
      fallbackOrder: 'Fallback Order',
      viewDocs: 'View Documentation',
      models: 'Available Models',
    },
    email: {
      title: 'Email Settings',
      smtpConfiguration: 'SMTP Configuration',
      testEmailConnection: 'Test Email Connection',
      testEmailAddress: 'Test Email Address',
      testEmailPlaceholder: 'test@example.com',
      sendTestEmail: 'Send Test Email',
      sending: 'Sending...',
      testEmailHint: 'Send a test email to verify your SMTP configuration.',
      testEmailSent: 'Test email sent to {email}',
      enterTestEmail: 'Please enter a test email address',
      fields: {
        smtpHost: 'SMTP Host',
        smtpHostDescription: 'SMTP server hostname (e.g., smtp.gmail.com)',
        smtpPort: 'SMTP Port',
        smtpPortDescription: 'Common: 587 (TLS), 465 (SSL), 25 (unencrypted)',
        username: 'Username',
        password: 'Password',
        fromAddress: 'From Email Address',
        fromAddressDescription: 'Sender email address',
        fromName: 'From Name',
        fromNameDescription: 'Sender display name',
      },
      testConnection: 'Test Connection',
      testSuccess: 'Connection successful',
      testFailed: 'Connection failed',
      settingsSaved: 'Email settings saved',
      settingsReset: 'Email settings reset to defaults',
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
      exportToVault: 'Export to Vault',
      exportToPath: 'Export to Path',
      exportButton: 'Export All Digests to {name}',
      exporting: 'Exporting...',
      exportSuccess: 'Exported {count} files to {path}',
      exportEmpty: 'No digests to export',
      exportError: 'Export failed',
      exporterNotEnabled: 'Exporter is not enabled',
      enableExporterFirst: 'Enable the exporter using the toggle above before exporting.',
      noExporters: 'No exporters available',
      noExportersDescription: 'Export formats will appear here once they are registered.',
      checkInstallation: 'Check your installation or contact support if exporters are missing.',
      settingsSaved: 'Export settings saved',
      settingsReset: 'Export settings reset to defaults',
      exporterSettingsSaved: '{name} settings saved',
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
      status: {
        active: 'Active',
        misconfigured: 'Misconfigured',
        disabled: 'Disabled',
        notConfigured: 'Not Configured',
      },
      configureRequired: 'Configure required fields first',
      disableExporter: 'Disable exporter',
      enableExporter: 'Enable exporter',
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
    // Common settings actions
    save: 'Save Settings',
    saved: 'Settings saved',
    saveChanges: 'Save Changes',
    saveConfiguration: 'Save Configuration',
    resetToDefaults: 'Reset to Defaults',
    settingsResetToDefaults: 'Settings reset to defaults',
    failedToSave: 'Failed to save settings',
    failedToReset: 'Failed to reset settings',
    // Source indicators
    source: {
      saved: 'Saved',
      env: 'ENV',
      default: 'Default',
      database: 'DB',
      environment: 'ENV',
      setViaEnv: 'Set via environment variable',
      valueFrom: 'Value from: {source}',
    },
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
        // Install source badges
        sourceGitHub: 'GitHub',
        sourcePyPI: 'PyPI',
        sourceLocal: 'Local',
        viewSource: 'View Source',
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
    optional: 'optional',
    all: 'All',
    noResults: 'No results found',
    darkMode: 'Dark Mode',
    lightMode: 'Light Mode',
    // Reusable labels
    labels: {
      status: 'Status',
      duration: 'Duration',
      tokens: 'Tokens',
      items: 'Items',
      cost: 'Cost',
      version: 'Version',
    },
    // Reusable actions
    actions: {
      refresh: 'Refresh',
      configure: 'Configure',
      test: 'Test',
      submit: 'Submit',
      clear: 'Clear',
    },
    // Pagination
    pagination: {
      previous: 'Previous',
      next: 'Next',
      pageOf: 'Page {page} of {total}',
    },
    // Bulk actions
    bulk: {
      selected: '{count} {entity} selected',
      clear: 'Clear',
      delete: 'Delete',
      deleting: 'Deleting...',
    },
    // Empty state
    empty: {
      title: 'No items found',
      message: 'Items will appear here once they are created.',
    },
    // Error state
    errorState: {
      loadFailed: 'Failed to load {entity}',
      unknownError: 'An unknown error occurred',
      tryAgain: 'Try Again',
    },
    // Tag input
    tagInput: {
      placeholder: 'Add tag...',
      create: 'Create "{value}"',
      digests: '{count} digests',
    },
    // Export dropdown
    exportDropdown: {
      button: 'Export',
      exporting: 'Exporting...',
      title: 'Export digest',
    },
    // View mode
    viewMode: {
      card: 'Card view',
      table: 'Table view',
    },
    // Tag filter
    tagFilter: {
      allTags: 'All Tags',
      loading: 'Loading...',
      noTags: 'No tags found',
      confirmDelete: 'Remove from {count} digests?',
      yes: 'Yes',
      no: 'No',
      deleteUnused: 'Delete unused ({count})',
      deleting: 'Deleting...',
    },
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

  // Onboarding
  onboarding: {
    emptyStates: {
      digests: {
        title: 'No digests yet',
        message: 'Digests are AI-generated summaries of content from your feeds. Run a feed to see digests here.',
        cta: 'View your feeds',
        tip: 'You can also search and filter digests once you have some.',
      },
      feeds: {
        title: 'No feeds yet',
        message: 'Feeds combine multiple sources and run them on a schedule to generate digests.',
        cta: 'Create a feed',
        tip: 'Start with one source, you can add more later.',
      },
      sources: {
        title: 'No sources yet',
        message: 'Sources are the RSS feeds, YouTube channels, or websites you want to follow.',
        cta: 'Add a source',
        tip: 'Try adding your favorite tech blog or newsletter.',
      },
    },
    wizard: {
      title: 'Welcome to Reconly',
      subtitle: "Let's set up your first feed",
      steps: {
        welcome: {
          title: 'Welcome',
          description: "We'll walk you through creating your first feed in just a few steps.",
          items: ['Add a source (RSS feed)', 'Create a feed', 'Run it to generate summaries'],
          llmWarning: "To generate summaries, you'll need to configure an LLM provider in Settings.",
          start: "Let's go!",
          skip: 'Skip for now',
        },
        source: {
          title: 'Add a Source',
          description: 'This RSS feed shows trending GitHub repositories.',
          nameLabel: 'Name',
          urlLabel: 'URL',
          namePlaceholder: 'GitHub Trending',
          urlDefault: 'https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml',
          create: 'Create Source',
          creating: 'Creating...',
        },
        feed: {
          title: 'Create a Feed',
          description: 'A feed runs your sources and summarizes new content.',
          nameLabel: 'Feed Name',
          namePlaceholder: 'My First Feed',
          sourceLabel: 'Source',
          create: 'Create Feed',
          creating: 'Creating...',
        },
        run: {
          title: 'Run Your Feed',
          description: 'Generating summaries...',
          running: 'Running...',
          completed: 'Done! Your first digest is ready.',
          noLlm: 'LLM not configured. Configure in Settings, then run your feed.',
          viewResults: 'View Results',
          goToSettings: 'Go to Settings',
        },
      },
      stepIndicator: 'Step {current} of {total}',
      skip: 'Skip',
      back: 'Back',
      next: 'Next',
    },
  },

  // Authentication
  auth: {
    login: {
      title: 'Sign In',
      subtitle: 'Enter your password to continue',
      password: 'Password',
      submit: 'Sign In',
      submitting: 'Signing in...',
      passwordRequired: 'Please enter a password',
      failed: 'Login failed. Please try again.',
      protected: 'This instance is password protected.',
    },
    logout: 'Sign Out',
  },

  // Time
  time: {
    justNow: 'Just now',
    minutesAgo: '{count}m ago',
    hoursAgo: '{count}h ago',
    daysAgo: '{count}d ago',
    never: 'Never',
  },

  // Sync Status
  syncStatus: {
    lastSync: 'Last sync',
    neverSynced: 'Never',
    justNow: 'Just now',
    healthyFeeds: 'Healthy feeds',
    failingFeeds: 'Failing feeds',
    feedsNeedAttention: 'feeds need attention',
  },

  // Chat
  chat: {
    title: 'Chat',
    askAI: 'Ask AI',
    newConversation: 'New Chat',
    quickChat: 'Quick Chat',
    openFullChat: 'Open full chat',
    noConversations: 'No conversations yet',
    startConversation: 'Start a Conversation',
    welcomeTitle: 'Welcome to Chat',
    welcomeDescription: 'Start a new conversation or select an existing one from the sidebar. I can help you manage your feeds, search digests, and answer questions about your content.',
    emptyTitle: 'Start a Conversation',
    emptyDescription: 'Ask me anything about your feeds, digests, or sources. I can help you search, create, and manage your content.',
    inputPlaceholder: 'Ask a question...',
    poweredBy: 'Powered by your configured LLM',
    deleteConfirm: 'Delete this conversation? This cannot be undone.',
    thinking: 'Thinking...',
    calling: 'Calling {tool}...',
    // Tool call labels
    toolCall: {
      arguments: 'Arguments:',
      result: 'Result:',
      error: 'Error:',
    },
  },

  // Dynamic Config Form
  dynamicForm: {
    // Placeholders
    pathPlaceholder: 'Enter path...',
    selectPlaceholder: 'Select an option...',
    secretPlaceholder: 'Enter value...',
    // Actions
    showSecret: 'Show value',
    hideSecret: 'Hide value',
    // Source indicators
    setViaEnv: 'ENV',
    // Validation messages
    validation: {
      required: 'This field is required',
      invalidNumber: 'Please enter a valid number',
      minValue: 'Value must be at least {min}',
      maxValue: 'Value must be at most {max}',
      formInvalid: 'Please fix the validation errors before saving',
    },
    // Empty state
    noFields: 'No configuration fields available.',
  },
} as const;

export type Strings = typeof strings;
