import sqlite3

conn = sqlite3.connect('data/governance.db')
conn.row_factory = sqlite3.Row

with open('scratch/community_dump.txt', 'w', encoding='utf-8') as f:
    f.write('# All Generated Workflow Names\n')
    cursor = conn.execute('SELECT display_name, cluster_size, community_id FROM workflows ORDER BY cluster_size DESC')
    wfs = [dict(r) for r in cursor.fetchall()]
    for row in wfs:
        f.write(f'- {row["display_name"]} ({row["cluster_size"]})\n')

    f.write('\n# Sample Communities\n')
    target_names = ["Update", "System", "Account"]
    for target in target_names:
        cursor = conn.execute('SELECT id, display_name, community_id FROM workflows WHERE display_name LIKE ? LIMIT 1', (f'%{target}%',))
        row = cursor.fetchone()
        if row:
            f.write(f'\n## Workflow: {row["display_name"]}\n')
            c_cursor = conn.execute('SELECT method, url FROM endpoints WHERE community_id = ? ORDER BY url LIMIT 20', (row["community_id"],))
            for ep in c_cursor.fetchall():
                f.write(f'  {ep["method"]} {ep["url"]}\n')
