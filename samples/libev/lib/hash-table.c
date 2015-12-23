#include <stdlib.h>
#include <string.h>

#include "base.h"
#include "hash-table.h"
#include "view.h"


void hash_table_init(struct hash_table *table, hash_func hash_func, size_t size)
{
	table->hash_func = hash_func;
	table->size = size;
	memset(table->table, 0, size * sizeof(struct list *));
}


static struct list **_hash(struct hash_table *table, struct ro_view key)
{
	return &table->table[table->hash_func(key) % table->size];
}


static struct list *_find(struct list *list, struct ro_view key)
{
	while (list) {
		struct hash_table_entry *entry = container_of(list, struct hash_table_entry, list);
		if (view_equal(key, entry->key))
			return list;
		list = list->next;
	}
	return NULL;
}


bool hash_table_has(struct hash_table *table, struct ro_view key)
{
	return _find(*_hash(table, key), key) != NULL;
}


struct rw_view hash_table_get(struct hash_table *table, struct ro_view key)
{
	struct list **head = _hash(table, key);
	struct list *list = _find(*head, key);
	if (!list)
		return (struct rw_view){0};
	return container_of(list, struct hash_table_entry, list)->value;
}


bool hash_table_put(struct hash_table *table,
		struct hash_table_entry *new_entry,
		struct hash_table_entry *old_entry)
{
	struct list **head = _hash(table, new_entry->key);
	struct list *list = _find(*head, new_entry->key);
	bool replace = list != NULL;
	struct hash_table_entry *entry;
	if (replace) {
		entry = container_of(list, struct hash_table_entry, list);
		old_entry->key = entry->key;
		old_entry->value = entry->value;
	} else {
		entry = expect(malloc(sizeof(struct hash_table_entry)));
		list_insert(head, memset(&entry->list, 0, sizeof(struct list)));
	}
	entry->key = new_entry->key;
	entry->value = new_entry->value;
	return replace;
}


bool hash_table_pop(struct hash_table *table,
		struct ro_view key,
		struct hash_table_entry *old_entry)
{
	struct list **head = _hash(table, key);
	struct list *list = _find(*head, key);
	if (!list)
		return false;
	struct hash_table_entry *entry = container_of(list, struct hash_table_entry, list);
	old_entry->key = entry->key;
	old_entry->value = entry->value;
	list_remove(head, list);
	free(entry);
	return true;
}
