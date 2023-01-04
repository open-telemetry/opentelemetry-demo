package org.daocloud.springcloud.adservice.dto;

public class Advertise {
    private Integer id;

    private String content;

    public Integer getId() {
        return id;
    }

    public void setId(final Integer id) {
        this.id = id;
    }

    public String getContent() {
        return content;
    }

    public void setContent(final String content) {
        this.content = content;
    }
}
