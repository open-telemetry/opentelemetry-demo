package io.daocloud.dataservice.controller;

import io.daocloud.dataservice.entity.Advertise;
import io.daocloud.dataservice.repository.AdvertiseRepository;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller    // This means that this class is a Controller
@RequestMapping(path = "/ad") // This means URL's start with /ad (after Application path)
public class AdvertiseController {
    private AdvertiseRepository advertiseRepository;

    public AdvertiseController(final AdvertiseRepository advertiseRepository) {
        this.advertiseRepository = advertiseRepository;
    }

    @PostMapping(path = "/add") // Map ONLY POST Requests
    public @ResponseBody
    String addNewUser(@RequestParam String content) {
        Advertise n = new Advertise();
        n.setContent(content);
        advertiseRepository.save(n);
        return "Saved";
    }

    @GetMapping(path = "/all")
    @ResponseBody
    public Iterable<Advertise> getAllAds() {
        // This returns a JSON or XML with the users
        return advertiseRepository.findAll();
    }

    @GetMapping(path = "/{id}")
    @ResponseBody
    public Advertise getAdById(@PathVariable("id") int id) {
        // This returns a JSON or XML with the users
        return advertiseRepository.findById(id).orElse(new Advertise());
    }
}
