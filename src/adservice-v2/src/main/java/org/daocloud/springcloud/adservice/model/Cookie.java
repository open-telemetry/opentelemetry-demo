package org.daocloud.springcloud.adservice.model;

import org.springframework.lang.Nullable;

import java.time.Duration;

/**
 * @author yangyang
 * @date 2023/2/24 上午11:28
 */
public class Cookie {
    private String name;
    private String value;
    private Duration maxAge = Duration.ofSeconds(-1);
    private String domain;
    private String path;

    private boolean secure;

    private boolean httpOnly;

    private String sameSite;


    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }

    public Duration getMaxAge() {
        return maxAge;
    }

    public void setMaxAge(Duration maxAge) {
        this.maxAge = maxAge;
    }

    public String getDomain() {
        return domain;
    }

    public void setDomain(String domain) {
        this.domain = domain;
    }

    public String getPath() {
        return path;
    }

    public void setPath(String path) {
        this.path = path;
    }

    public boolean isSecure() {
        return secure;
    }

    public void setSecure(boolean secure) {
        this.secure = secure;
    }

    public boolean isHttpOnly() {
        return httpOnly;
    }

    public void setHttpOnly(boolean httpOnly) {
        this.httpOnly = httpOnly;
    }

    public String getSameSite() {
        return sameSite;
    }

    public void setSameSite(String sameSite) {
        this.sameSite = sameSite;
    }

    @Override
    public String toString() {
        return "Cookie{" +
                "name='" + name + '\'' +
                ", value='" + value + '\'' +
                ", maxAge=" + maxAge +
                ", domain='" + domain + '\'' +
                ", path='" + path + '\'' +
                ", secure=" + secure +
                ", httpOnly=" + httpOnly +
                ", sameSite='" + sameSite + '\'' +
                '}';
    }
}
