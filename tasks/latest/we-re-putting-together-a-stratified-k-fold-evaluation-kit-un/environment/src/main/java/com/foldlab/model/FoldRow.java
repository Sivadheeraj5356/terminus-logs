package com.foldlab.model;

public final class FoldRow {
    private final String id;
    private final String label;

    public FoldRow(String id, String label) {
        this.id = id;
        this.label = label;
    }

    public String getId() {
        return id;
    }

    public String getLabel() {
        return label;
    }
}
