CREATE TABLE audit_log (
	id INTEGER NOT NULL, 
	ts VARCHAR NOT NULL, 
	actor_id INTEGER, 
	action VARCHAR NOT NULL, 
	doc_id INTEGER, 
	result VARCHAR NOT NULL, 
	detail VARCHAR, 
	prev_hash VARCHAR NOT NULL, 
	hash VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	token_version INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);

CREATE TABLE documents (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	category VARCHAR, 
	storage_key VARCHAR NOT NULL, 
	sha256 VARCHAR, 
	size INTEGER, 
	created_at DATETIME, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE permissions (
	id INTEGER NOT NULL, 
	doc_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	level VARCHAR NOT NULL, 
	granted_by INTEGER, 
	created_at DATETIME, 
	revoked_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(doc_id) REFERENCES documents (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(granted_by) REFERENCES users (id)
);
